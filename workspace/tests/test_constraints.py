from attack import _valid_candidate


def test_valid_single_message():
    assert _valid_candidate(("hello",)) is True


def test_rejects_empty():
    assert _valid_candidate(()) is False


def test_rejects_too_many_messages():
    assert _valid_candidate(("x",) * 33) is False


def test_accepts_max_messages():
    assert _valid_candidate(("x",) * 32) is True


def test_rejects_message_too_long():
    assert _valid_candidate(("x" * 2001,)) is False


def test_accepts_message_at_limit():
    assert _valid_candidate(("x" * 2000,)) is True


def test_rejects_empty_string_message():
    assert _valid_candidate(("",)) is False


def test_rejects_whitespace_message():
    assert _valid_candidate((" ",)) is False


def test_v6_constants():
    import attack
    assert attack.REPLAY_SAFE_FRAC == 0.97
    assert attack.MULTIPOST_N == 4
    assert attack.MULTIPOST_REPLAY_COEF == 1.0
    assert attack.PROBE_HOPS == 8          # V8: full-hop probe
    assert attack.EDGE_MARGIN_FLOOR_S == 4.0  # V8: aggressive floor
    assert attack.MARGIN_FRAC == 0.05        # V8: fill 95% of budget
