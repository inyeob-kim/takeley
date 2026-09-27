"""Reddit / HN / Trends / Official parse and module isolation."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.discovery.modules.official_module import OfficialSourceModule
from app.discovery.modules.reddit_module import RedditSourceModule
from app.discovery.modules.trends_module import TrendsSourceModule
from app.discovery.protocol import IngestContext
from app.discovery.relevance import filter_issue_relevant, is_issue_relevant
from app.providers.hacker_news_provider import parse_hn_item
from app.providers.reddit_provider import parse_reddit_listing
from app.providers.sec_atom_provider import is_routine_sec_title, parse_sec_atom
from app.providers.trends_provider import parse_trends_xml


TRENDS_XML = """<?xml version="1.0"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item>
      <title>Federal Reserve</title>
      <ht:approx_traffic>200000+</ht:approx_traffic>
      <ht:news_item>
        <ht:news_item_title>Fed holds rates steady after policy meeting</ht:news_item_title>
        <ht:news_item_snippet>The Federal Reserve left interest rates unchanged.</ht:news_item_snippet>
        <ht:news_item_url>https://example.com/fed?utm_source=trends</ht:news_item_url>
        <ht:news_item_source>Reuters</ht:news_item_source>
      </ht:news_item>
    </item>
  </channel>
</rss>
"""

SEC_ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>ACME INC (0000001) (8-K)</title>
    <id>urn:tag:sec.gov,2024:accession-number=000-1</id>
    <updated>2024-01-02T12:00:00Z</updated>
    <link href="https://www.sec.gov/Archives/edgar/data/1/000-1-index.htm"/>
    <summary>Current report</summary>
  </entry>
  <entry>
    <title>4 - Bernes Marshall (0002045034) (Reporting)</title>
    <id>urn:tag:sec.gov,2008:accession-number=form4</id>
    <updated>2024-01-02T12:00:00Z</updated>
    <link href="https://www.sec.gov/Archives/edgar/data/2/form4.htm"/>
    <summary>Statement of changes in beneficial ownership</summary>
  </entry>
</feed>
"""


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _ctx(db):
    from app.db.repositories import CursorRepository, RawItemRepository

    return IngestContext(
        raw_repo=RawItemRepository(db),
        cursor_repo=CursorRepository(db),
        universe=[],
        us_universe=[],
        kr_universe=[],
    )


def test_parse_reddit_listing():
    payload = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "abc123",
                        "title": "Markets open mixed after jobs report",
                        "selftext": "Futures pointed higher overnight.",
                        "permalink": "/r/business/comments/abc123/x/",
                        "url": "https://www.reddit.com/r/business/comments/abc123/x/",
                        "author": "wire",
                        "subreddit": "business",
                        "created_utc": 1700000000,
                        "ups": 120,
                        "num_comments": 18,
                    }
                }
            ]
        }
    }
    items = parse_reddit_listing(payload, subreddit="business")
    assert len(items) == 1
    assert items[0].provider.value == "reddit"
    assert items[0].external_id == "abc123"
    assert items[0].raw_payload["source"] == "reddit"
    assert items[0].raw_payload["metrics"]["reply_count"] == 18


def test_parse_hn_item_skips_deleted():
    assert parse_hn_item({"id": 1, "title": "x", "deleted": True}) is None
    item = parse_hn_item(
        {
            "id": 42,
            "title": "Show HN: A new market data tool",
            "url": "https://example.com/hn",
            "by": "pg",
            "time": 1700000000,
            "score": 88,
            "descendants": 12,
        }
    )
    assert item is not None
    assert item.provider.value == "hacker_news"
    assert item.external_id == "42"
    assert item.raw_payload["source"] == "hacker_news"


def test_parse_trends_news_item():
    items = parse_trends_xml(TRENDS_XML, geo="US")
    assert len(items) == 1
    assert items[0].provider.value == "news"
    assert items[0].raw_payload["source"] == "search_trends"
    assert items[0].raw_payload["trend_query"] == "Federal Reserve"
    assert items[0].raw_payload["canonical_url"] == "https://example.com/fed"


def test_parse_sec_atom():
    items = parse_sec_atom(SEC_ATOM, form="8-K")
    assert len(items) == 1
    assert items[0].provider.value == "official"
    assert items[0].raw_payload["source"] == "sec_edgar"
    assert "8-K" in (items[0].title or "")
    assert is_routine_sec_title("4 - Bernes Marshall (0002045034) (Reporting)") is True


def test_trends_and_entertainment_relevance():
    assert is_issue_relevant("Fed holds rates after policy meeting") is True
    assert is_issue_relevant("Nicole Kidman urges fans to demand Lioness season 4") is False
    assert is_issue_relevant("자정 넘어 시작된 배드민턴 경기") is False
    items = parse_trends_xml(TRENDS_XML, geo="US")
    kept = filter_issue_relevant(items)
    assert kept
    assert "Fed" in (kept[0].title or "")


def test_reddit_module_isolates_subreddit_failure(monkeypatch):
    from app.db.repositories import RawItemRepository

    db = _db()
    ctx = _ctx(db)

    def fake_fetch(self, subreddit, *, limit=15):
        if subreddit == "news":
            raise RuntimeError("http 503")
        return parse_reddit_listing(
            {
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": "ok1",
                                "title": "Federal Reserve holds interest rates after policy meeting",
                                "selftext": "Enough text for a listing body.",
                                "permalink": "/r/business/comments/ok1/",
                                "author": "a",
                                "subreddit": "business",
                                "created_utc": 1700000000,
                            }
                        }
                    ]
                }
            },
            subreddit=subreddit,
        )

    monkeypatch.setattr(
        "app.discovery.modules.reddit_module.get_settings",
        lambda: type("S", (), {"reddit_subreddits": "news,business", "reddit_limit_per_sub": 5})(),
    )
    monkeypatch.setattr(
        "app.discovery.modules.reddit_module.RedditProvider.configured",
        lambda self: True,
    )
    monkeypatch.setattr(
        "app.discovery.modules.reddit_module.RedditProvider.fetch_subreddit",
        fake_fetch,
    )
    result = RedditSourceModule().run(db, ctx)
    assert result.failed == 1
    assert result.inserted == 1
    assert RawItemRepository(db).unprocessed(limit=10)


def test_trends_module_isolates_geo_failure(monkeypatch):
    db = _db()
    ctx = _ctx(db)

    def fake_geo(self, geo, *, limit=40):
        if geo == "KR":
            raise RuntimeError("timeout")
        return parse_trends_xml(TRENDS_XML, geo=geo)

    monkeypatch.setattr(
        "app.discovery.modules.trends_module.get_settings",
        lambda: type("S", (), {"trends_geos": "KR,US"})(),
    )
    monkeypatch.setattr(
        "app.discovery.modules.trends_module.TrendsProvider.fetch_geo",
        fake_geo,
    )
    result = TrendsSourceModule().run(db, ctx)
    assert result.failed == 1
    assert result.inserted == 1


def test_official_sec_failure_does_not_block_empty_dart(monkeypatch):
    db = _db()
    ctx = _ctx(db)

    def boom(*args, **kwargs):
        raise RuntimeError("sec 403")

    monkeypatch.setattr(
        "app.discovery.modules.official_module.get_settings",
        lambda: type(
            "S",
            (),
            {
                "official_sec_enabled": True,
                "dart_api_key": "",
                "official_dart_symbol_cap": 12,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.discovery.modules.official_module.SecAtomProvider.fetch",
        boom,
    )
    result = OfficialSourceModule().run(db, ctx)
    assert result.failed == 1
    assert result.inserted == 0
    assert result.error


def test_reddit_module_skips_without_credentials(monkeypatch):
    db = _db()
    ctx = _ctx(db)
    monkeypatch.setattr(
        "app.discovery.modules.reddit_module.get_settings",
        lambda: type("S", (), {"reddit_subreddits": "news", "reddit_limit_per_sub": 5})(),
    )
    monkeypatch.setattr(
        "app.discovery.modules.reddit_module.RedditProvider.configured",
        lambda self: False,
    )
    result = RedditSourceModule().run(db, ctx)
    assert result.skipped_reason == "no_credentials"
