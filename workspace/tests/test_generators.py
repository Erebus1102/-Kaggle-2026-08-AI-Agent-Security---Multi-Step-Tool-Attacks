# workspace/tests/test_generators.py
import itertools

from attack import _url_stream, _recipient_stream, _domain_stream, is_clean


def test_domain_stream_unique_and_clean_within_pool():
    doms = list(itertools.islice(_domain_stream(), 900))
    assert len(doms) == len(set(doms))          # unique
    assert all(is_clean(d) for d in doms)       # clean
    assert len(doms) >= 864                     # pool + extensions


def test_url_stream_shape():
    urls = list(itertools.islice(_url_stream(), 5))
    for u in urls:
        assert u.startswith("https://") and u.endswith("/log")
        assert is_clean(u)


def test_recipient_stream_unique_and_clean():
    recips = list(itertools.islice(_recipient_stream(), 300))
    assert len(recips) == len(set(recips))
    assert all("@" in r and is_clean(r) for r in recips)
