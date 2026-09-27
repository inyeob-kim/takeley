"""RSS-only raw_items can become an Issue draft through Process V2. X is not required."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models import Event, RawItem, Signal
from app.db.session import Base
from worker.jobs.process_issues_v2 import run_process_issues_v2


RSS_TEXT = (
    "The Federal Reserve announced it will hold interest rates unchanged "
    "after the latest policy meeting, citing persistent inflation risk "
    "and a slower path for future cuts."
)


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_rss_only_process_creates_issue_draft(monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    db = _db()
    db.add(
        RawItem(
            provider="news",
            external_id="rss-fed-hold",
            title="Fed holds rates steady after policy meeting",
            text=RSS_TEXT,
            url="https://example.com/fed-holds",
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow(),
            processed=0,
            raw_payload={
                "source": "rss_feed",
                "feed_id": "feed-reuters",
                "guid": "g-fed-1",
                "canonical_url": "https://example.com/fed-holds",
            },
        )
    )
    db.commit()

    result = run_process_issues_v2(db)
    assert db.query(RawItem).filter(RawItem.provider == "x").count() == 0
    assert result["signals_created"] >= 1
    issue = db.query(Signal).one()
    assert issue.status == "draft"
    assert issue.lifecycle == "CANDIDATE"
    assert db.query(Event).count() == 1
    raw = db.query(RawItem).one()
    assert raw.processed == 1
    assert raw.raw_payload["source"] == "rss_feed"


def test_rss_matches_existing_issue_without_second_draft(monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    db = _db()
    first = RawItem(
        provider="x",
        external_id="x-fed-hold",
        title="Fed holds rates steady after policy meeting",
        text=RSS_TEXT,
        url="https://x.example/status/1",
        published_at=datetime.utcnow(),
        fetched_at=datetime.utcnow(),
        processed=0,
        raw_payload={"source_lane": "global"},
    )
    db.add(first)
    db.commit()
    created = run_process_issues_v2(db)
    assert created["signals_created"] >= 1
    assert db.query(Signal).count() == 1

    db.add(
        RawItem(
            provider="news",
            external_id="rss-fed-hold",
            title="Fed holds rates steady after policy meeting",
            text=RSS_TEXT,
            url="https://example.com/fed-holds",
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow(),
            processed=0,
            raw_payload={
                "source": "rss_feed",
                "feed_id": "feed-bbc",
                "guid": "g-fed-bbc",
                "canonical_url": "https://example.com/fed-holds",
            },
        )
    )
    db.commit()
    second = run_process_issues_v2(db)
    assert db.query(Signal).count() == 1
    assert second["signals_created"] == 0
    assert second["signals_updated"] >= 1
