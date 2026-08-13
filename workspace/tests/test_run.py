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
