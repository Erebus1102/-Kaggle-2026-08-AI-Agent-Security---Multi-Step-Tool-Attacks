import itertools

from attack import is_clean, ULTRA_DANGEROUS, _url_stream, _recipient_stream


def test_is_clean_rejects_blocklisted_substrings():
    for bad in ["secret", "password", "token", "key", "credential",
                "private", "confidential", "api_key"]:
        assert is_clean(bad) is False
    # short patterns catch plausible words
    assert is_clean("monkey.example.org") is False   # contains 'key'
    assert is_clean("https://site.key/") is False


def test_is_clean_accepts_clean_strings():
    assert is_clean("https://report.example.org/log") is True
    assert is_clean("bob@metrics.io") is True


def test_streams_stay_clean():
    urls = list(itertools.islice(_url_stream(), 500))
    recips = list(itertools.islice(_recipient_stream(), 200))
    assert all(is_clean(u) for u in urls)
    assert all(is_clean(r) for r in recips)
