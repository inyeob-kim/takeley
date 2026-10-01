import base64

from app.providers.article_fetch import (
    _decode_google_news_article_id,
    extract_article_text,
)


def test_decode_google_news_embeds_publisher_url():
    inner = b"https://www.barrons.com/articles/tesla-stock-musk-ai-123"
    # Pad with junk bytes like Google's opaque id payloads.
    blob = b"\x08\x13" + inner + b"\x10\x01"
    article_id = base64.urlsafe_b64encode(blob).decode("ascii").rstrip("=")
    assert _decode_google_news_article_id(article_id) == inner.decode("ascii")


def test_is_publisher_host_rejects_googleusercontent():
    from app.providers.article_fetch import _is_publisher_host

    assert _is_publisher_host("finance.yahoo.com")
    assert not _is_publisher_host("lh3.googleusercontent.com")
    assert not _is_publisher_host("news.google.com")


def test_news_drops_items_without_body(monkeypatch):
    from app.domain.models import RawItem, SourceType
    from app.providers.article_fetch import ArticleBody
    from app.providers.news_provider import NewsProvider

    provider = NewsProvider()
    provider.fetch_body = True

    rss_item = RawItem(
        provider=SourceType.NEWS,
        external_id="a1",
        url="https://news.google.com/rss/articles/x",
        title="Tesla Stock Drops",
        text="Tesla Stock Drops - barrons.com",
        raw_payload={"source": "rss"},
    )

    monkeypatch.setattr(
        "app.providers.article_fetch.fetch_article_body",
        lambda *a, **k: ArticleBody(text="", canonical_url=None, ok=False, reason="too_short"),
    )
    assert provider._enrich_with_body(rss_item) is None


def test_news_keeps_items_with_body(monkeypatch):
    from app.domain.models import RawItem, SourceType
    from app.providers.article_fetch import ArticleBody
    from app.providers.news_provider import NewsProvider

    provider = NewsProvider()
    provider.fetch_body = True
    rss_item = RawItem(
        provider=SourceType.NEWS,
        external_id="a1",
        url="https://example.com/tesla",
        title="Tesla Stock Drops",
        text="Tesla Stock Drops - example",
        raw_payload={"source": "rss"},
    )
    body = (
        "Tesla shares were down 1.3% at $360.75 in early trading after Musk "
        "joined those concerned about AI. Other AI names also declined."
    )
    monkeypatch.setattr(
        "app.providers.article_fetch.fetch_article_body",
        lambda *a, **k: ArticleBody(
            text=body,
            canonical_url="https://example.com/tesla",
            ok=True,
            image_url="https://cdn.example.com/hero.jpg",
        ),
    )
    out = provider._enrich_with_body(rss_item)
    assert out is not None
    assert "360.75" in out.text
    assert out.raw_payload.get("body_ok") is True
    assert out.raw_payload.get("image_url") == "https://cdn.example.com/hero.jpg"


def test_extract_article_image_og_and_rejects_pixel():
    from app.providers.article_fetch import extract_article_image

    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.example.com/story.jpg" />
      <meta name="twitter:image" content="https://cdn.example.com/1x1.gif" />
    </head></html>
    """
    assert extract_article_image(html) == "https://cdn.example.com/story.jpg"

    bad = '<meta property="og:image" content="https://ads.example.com/pixel.gif" />'
    assert extract_article_image(bad) is None


def test_rss_feed_drops_items_without_body(monkeypatch):
    from app.domain.models import RawItem, SourceType
    from app.providers.article_fetch import ArticleBody
    from app.providers.rss_feed_provider import RssFeedProvider

    provider = RssFeedProvider()
    provider.fetch_body = True
    item = RawItem(
        provider=SourceType.NEWS,
        external_id="r1",
        url="https://news.google.com/rss/articles/x",
        title="Apple stock pops",
        text="Apple stock pops - Yahoo Finance Bloomberg 9to5Mac",
        raw_payload={"source": "rss_feed"},
    )
    monkeypatch.setattr(
        "app.providers.article_fetch.fetch_article_body",
        lambda *a, **k: ArticleBody(text="", canonical_url=None, ok=False, reason="too_short"),
    )
    assert provider._enrich_feed_items([item]) == []


def test_rss_feed_keeps_items_with_body(monkeypatch):
    from app.domain.models import RawItem, SourceType
    from app.providers.article_fetch import ArticleBody
    from app.providers.rss_feed_provider import RssFeedProvider

    provider = RssFeedProvider()
    provider.fetch_body = True
    item = RawItem(
        provider=SourceType.NEWS,
        external_id="r1",
        url="https://finance.yahoo.com/news/apple",
        title="Apple stock pops on report",
        text="Apple stock pops - Yahoo Finance Bloomberg",
        raw_payload={"source": "rss_feed"},
    )
    body = (
        "Apple (AAPL) stock rose in early trading following a report that the "
        "company is preparing to host an event outlining its entry into the "
        "smart home space. According to Bloomberg, Apple will unveil a hub."
    )
    monkeypatch.setattr(
        "app.providers.article_fetch.fetch_article_body",
        lambda *a, **k: ArticleBody(
            text=body,
            canonical_url="https://finance.yahoo.com/news/apple",
            ok=True,
        ),
    )
    kept = provider._enrich_feed_items([item])
    assert len(kept) == 1
    assert "smart home space" in kept[0].text
    assert kept[0].raw_payload.get("body_ok") is True
    assert kept[0].raw_payload.get("rss_text")  # original snippet preserved
