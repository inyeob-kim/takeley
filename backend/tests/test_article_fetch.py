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
        "app.providers.news_provider.fetch_article_body",
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
        "app.providers.news_provider.fetch_article_body",
        lambda *a, **k: ArticleBody(
            text=body,
            canonical_url="https://example.com/tesla",
            ok=True,
        ),
    )
    out = provider._enrich_with_body(rss_item)
    assert out is not None
    assert "360.75" in out.text
    assert out.raw_payload.get("body_ok") is True
