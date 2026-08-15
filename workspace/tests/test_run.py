# workspace/tests/test_run.py
import itertools

from attack import (
    AttackAlgorithm, _static_fallback, _url_stream,
    MIN_LIVE_BUDGET_S, MARGIN_FRAC, MAIN_FRAC, REPLAY_SAFE_FRAC,
    REPLAY_BUDGET_S, MAX_CANDIDATES,
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


def test_run_live_misses_still_fallback():
    # Live env healthy but 0 fires => fallback appended so replay has body.
    result = AttackAlgorithm().run(
        _FakeEnv(), AttackRunConfig(time_budget_s=300))
    assert len(result) >= 300                 # fallback body present


def test_run_search_disabled_uses_fallback():
    algo = AttackAlgorithm({"search_enabled": False})
    result = algo.run(_FakeEnv(), AttackRunConfig(time_budget_s=8750))
    assert result == _static_fallback()


def test_finalize_respects_candidate_cap():
    # run() 的最后防线是 _finalize 的 2000 上限(防御性,正常路径远达不到)
    from attack import _finalize

    class _C:
        def __init__(self, i):
            self.user_messages = (f"msg {i}",)

    many = [_C(i) for i in range(3000)]
    assert len(_finalize(many)) == MAX_CANDIDATES
