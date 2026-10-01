"""RSS XML parse, identity, canonical URL, 304, feed isolation."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import RawItem
from app.db.session import Base
from app.discovery.expire import expire_stale_rss_items
from app.discovery.modules.rss_module import RssSourceModule
from app.discovery.protocol import IngestContext
from app.providers.rss_feed_provider import (
    RssFetchResult,
    canonical_url,
    parse_rss_xml,
    rss_external_id,
)


SAMPLE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Demo</title>
    <item>
      <title>First</title>
      <link>https://example.com/a?utm_source=x&amp;id=1</link>
      <guid>g-1</guid>
      <description>Body one</description>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_canonical_url_strips_utm_keeps_other():
    assert canonical_url("https://ex.com/p?utm_source=tw&id=9") == "https://ex.com/p?id=9"


def test_parse_rss_uses_source_or_host_as_author():
    from app.providers.rss_feed_provider import publisher_label_from_url

    assert publisher_label_from_url("https://www.bbc.co.uk/news/x") == "BBC"
    xml = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Story</title>
      <link>https://news.google.com/rss/articles/abc</link>
      <guid>g-1</guid>
      <description>Body</description>
      <source url="https://www.bbc.co.uk">BBC News</source>
    </item>
  </channel>
</rss>
"""
    items = parse_rss_xml(xml, feed_id="demo")
    assert len(items) == 1
    assert items[0].author == "BBC News"


def test_parse_valid_xml_and_external_id():
    items = parse_rss_xml(SAMPLE, feed_id="feed-a")
    assert len(items) == 1
    assert items[0].provider.value == "news"
    assert items[0].raw_payload["source"] == "rss_feed"
    assert items[0].raw_payload["feed_id"] == "feed-a"
    assert items[0].raw_payload["guid"] == "g-1"
    assert items[0].raw_payload["canonical_url"] == "https://example.com/a?id=1"
    assert items[0].external_id == rss_external_id("feed-a", "g-1")


def test_empty_channel():
    xml = """<?xml version="1.0"?><rss><channel></channel></rss>"""
    assert parse_rss_xml(xml, feed_id="f") == []


def test_malformed_xml_raises():
    try:
        parse_rss_xml("<not-xml", feed_id="f")
    except Exception:
        return
    raise AssertionError("expected parse error")


def test_no_guid_uses_canonical_url():
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>T</title><link>https://ex.com/p?utm_medium=a</link><description>D</description></item>
    </channel></rss>"""
    items = parse_rss_xml(xml, feed_id="f1")
    assert items[0].external_id == rss_external_id("f1", "https://ex.com/p")


def test_no_guid_no_url_skipped():
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>T</title><description>D</description></item>
    </channel></rss>"""
    assert parse_rss_xml(xml, feed_id="f") == []


def test_same_guid_different_feeds_distinct():
    a = parse_rss_xml(SAMPLE, feed_id="feed-a")[0]
    b = parse_rss_xml(SAMPLE, feed_id="feed-b")[0]
    assert a.external_id != b.external_id


def test_same_feed_same_guid_same_id():
    a = parse_rss_xml(SAMPLE, feed_id="feed-a")[0]
    b = parse_rss_xml(SAMPLE, feed_id="feed-a")[0]
    assert a.external_id == b.external_id


def test_conditional_headers_and_304(monkeypatch):
    import httpx
    from app.providers.rss_feed_provider import RssFeedProvider

    seen = {}

    class FakeResp:
        def __init__(self, status, headers):
            self.status_code = status
            self.headers = headers
            self.text = ""

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            seen["headers"] = headers
            return FakeResp(304, {"etag": '"abc"', "last-modified": "Wed, 01 Jan 2025 00:00:00 GMT"})

    monkeypatch.setattr(httpx, "Client", FakeClient)
    result = RssFeedProvider().fetch_feed(
        feed_id="f",
        url="https://example.com/rss",
        etag='"old"',
        last_modified="Tue, 31 Dec 2024 00:00:00 GMT",
    )
    assert result.not_modified is True
    assert result.status_code == 304
    assert result.items == []
    assert seen["headers"]["If-None-Match"] == '"old"'
    assert seen["headers"]["If-Modified-Since"] == "Tue, 31 Dec 2024 00:00:00 GMT"


def test_http_500_raises(monkeypatch):
    import httpx
    from app.providers.rss_feed_provider import RssFeedProvider

    class FakeResp:
        status_code = 500
        headers = {}
        text = "nope"

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "500",
                request=httpx.Request("GET", "https://example.com/rss"),
                response=httpx.Response(500),
            )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            return FakeResp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    try:
        RssFeedProvider().fetch_feed(feed_id="f", url="https://example.com/rss")
    except httpx.HTTPStatusError:
        return
    raise AssertionError("expected HTTP 500")


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_expire_rss_only():
    db = _db()
    old = datetime.utcnow() - timedelta(hours=80)
    fresh = datetime.utcnow() - timedelta(hours=2)
    db.add(
        RawItem(
            provider="news",
            external_id="rss-old",
            text="old rss",
            fetched_at=old,
            processed=0,
            raw_payload={"source": "rss_feed", "feed_id": "a"},
        )
    )
    db.add(
        RawItem(
            provider="news",
            external_id="rss-new",
            text="new rss",
            fetched_at=fresh,
            processed=0,
            raw_payload={"source": "rss_feed", "feed_id": "a"},
        )
    )
    db.add(
        RawItem(
            provider="x",
            external_id="x-old",
            text="old tweet " * 8,
            fetched_at=old,
            processed=0,
            raw_payload={},
        )
    )
    db.add(
        RawItem(
            provider="news",
            external_id="ticker-old",
            text="old google news",
            fetched_at=old,
            processed=0,
            raw_payload={"source": "rss"},
        )
    )
    db.commit()
    assert expire_stale_rss_items(db) == 1
    rows = {row.external_id: row.processed for row in db.query(RawItem).all()}
    assert rows["rss-old"] == 1
    assert rows["rss-new"] == 0
    assert rows["x-old"] == 0
    assert rows["ticker-old"] == 0


def test_rss_module_isolates_feed_failure(monkeypatch):
    from app.db.models import RssFeed
    from app.db.repositories import CursorRepository, RawItemRepository

    db = _db()
    db.add(RssFeed(id="a", name="A", url="https://a.example/rss", enabled=True))
    db.add(RssFeed(id="b", name="B", url="https://b.example/rss", enabled=True))
    db.commit()

    def fake_fetch(self, *, feed_id, url, language="", etag=None, last_modified=None, limit=40):
        if feed_id == "a":
            raise RuntimeError("http 500")
        return RssFetchResult(items=parse_rss_xml(SAMPLE, feed_id=feed_id), status_code=200)

    monkeypatch.setattr(
        "app.discovery.modules.rss_module.RssFeedProvider.fetch_feed",
        fake_fetch,
    )
    ctx = IngestContext(
        raw_repo=RawItemRepository(db),
        cursor_repo=CursorRepository(db),
        universe=[],
        us_universe=[],
        kr_universe=[],
    )
    result = RssSourceModule().run(db, ctx)
    assert result.failed == 1
    assert result.inserted == 1
    feed_a = db.query(RssFeed).filter(RssFeed.id == "a").first()
    feed_b = db.query(RssFeed).filter(RssFeed.id == "b").first()
    assert feed_a.last_error
    assert feed_b.last_error is None


def test_rss_304_is_success(monkeypatch):
    from app.db.models import RssFeed
    from app.db.repositories import CursorRepository, RawItemRepository

    db = _db()
    db.add(
        RssFeed(
            id="a",
            name="A",
            url="https://a.example/rss",
            enabled=True,
            etag='"old"',
        )
    )
    db.commit()

    def fake_304(self, *, feed_id, url, language="", etag=None, last_modified=None, limit=40):
        return RssFetchResult(items=[], status_code=304, etag='"new"', not_modified=True)

    monkeypatch.setattr(
        "app.discovery.modules.rss_module.RssFeedProvider.fetch_feed",
        fake_304,
    )
    ctx = IngestContext(
        raw_repo=RawItemRepository(db),
        cursor_repo=CursorRepository(db),
        universe=[],
        us_universe=[],
        kr_universe=[],
    )
    result = RssSourceModule().run(db, ctx)
    assert result.error is None
    assert result.fetched == 0
    assert result.inserted == 0
    feed = db.query(RssFeed).filter(RssFeed.id == "a").first()
    assert feed.last_error is None
    assert feed.last_success_at is not None
    assert feed.etag == '"new"'
