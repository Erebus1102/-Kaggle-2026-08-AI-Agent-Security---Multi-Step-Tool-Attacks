from attack import is_clean, clean_urls, clean_recipients, ULTRA_DANGEROUS


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


def test_clean_urls_distinct_domains_and_all_clean():
    urls = clean_urls(50)
    assert len(urls) == 50
    assert len(urls) == len(set(urls))           # all distinct
    domains = {u.split("://", 1)[1].split("/", 1)[0] for u in urls}
    assert len(domains) == 50                     # distinct domain per URL
    assert all(is_clean(u) for u in urls)
    assert all(u.startswith("https://") for u in urls)


def test_clean_recipients_all_clean_and_distinct():
    recips = clean_recipients(20)
    assert len(recips) == 20
    assert len(recips) == len(set(recips))
    assert all("@" in r and is_clean(r) for r in recips)
