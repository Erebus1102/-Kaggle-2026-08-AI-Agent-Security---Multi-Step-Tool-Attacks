# workspace/tests/test_fallback.py
from attack import (
    _static_fallback, _valid_candidate, post_msg, deputy_msg,
    FALLBACK_POST_N, FALLBACK_DEPUTY_N,
)


def test_fallback_counts_and_validity():
    cands = _static_fallback()
    assert len(cands) == FALLBACK_POST_N + FALLBACK_DEPUTY_N
    assert all(_valid_candidate(c.user_messages) for c in cands)
    msgs = [c.user_messages[0] for c in cands]
    assert len(msgs) == len(set(msgs))       # all distinct
    assert sum(1 for m in msgs if m.startswith("Call http.post")) == FALLBACK_POST_N
    assert sum(1 for m in msgs if m.startswith("Forward the")) == FALLBACK_DEPUTY_N


def test_fallback_is_deterministic():
    assert _static_fallback() == _static_fallback()
