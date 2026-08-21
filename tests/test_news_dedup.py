from jafar.news_dedup import SeenNews, fingerprint


def test_same_title_and_url_is_seen_once():
    seen = SeenNews()
    item = fingerprint(" Новость  сегодня ", "https://example.test/a/")
    assert seen.add_if_new(item) is True
    assert seen.add_if_new(item) is False
