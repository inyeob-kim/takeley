"""Industry search overrides, rotation, dynamic limits, and the daily post cap."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import RawItem, XIngestConfig
from app.db.repositories import CursorRepository, RawItemRepository
from app.db.session import Base
from app.domain.models import RawItem as RawItemDomain
from app.domain.models import SourceType
from app.pipeline.dynamic_query import (
    active_dynamic_queries,
    arm_dynamic_topic,
    dynamic_search_queries,
    remember_topics,
    settle_dynamic_polls,
)
from app.pipeline.industries import ISSUE_INDUSTRY_KEYS, discovery_query_for
from app.pipeline.x_schedule import kst_day, posts_fetched_today
from app.services.industry_search_config import (
    fallback_plans,
    frequency_due,
    load_plans,
    parse_keyword_list,
    select_rotation_lanes,
    topic_query_cursor_key,
    update_industries,
)
from worker.jobs.ingest import _stop_for_daily_budget


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_empty_table_matches_industries_py():
    db = _db()
    assert load_plans(db) is None
    for plan in fallback_plans():
        assert plan.query_ko == discovery_query_for(plan.key, "korea")
        assert plan.query_en == discovery_query_for(plan.key, "global")


def test_keyword_save_rejects_operators():
    with pytest.raises(ValueError):
        parse_keyword_list("국회 OR 대통령")
    db = _db()
    db.add(XIngestConfig(id="default", industries="politics,ai"))
    db.commit()
    with pytest.raises(ValueError):
        update_industries(
            db, [{"industry_key": "politics", "keywords_ko": "lang:ko"}]
        )


def test_rotation_skips_disabled_and_keeps_high_opposite_only():
    from dataclasses import replace

    plans = [
        replace(plan, enabled=False) if plan.key == "sports" else plan
        for plan in fallback_plans()
    ]
    lanes = select_rotation_lanes(
        plans, "korea", scan_index=1, limit=10, opposite_count=2
    )
    pairs = [(lane.industry_key, lane.source_lane) for lane in lanes]
    assert ("sports", "korea") not in pairs
    assert ("finance", "korea") not in pairs
    assert ("culture", "korea") not in pairs
    assert ("politics", "korea") in pairs
    assert ("economy", "korea") in pairs
    assert ("ai", "korea") in pairs
    opposite = [key for key, lane in pairs if lane == "global"]
    assert opposite == ["politics", "economy"]
    assert frequency_due("every_3", 0) is True
    assert frequency_due("every_3", 1) is False
    assert frequency_due("every_2", 2) is True


def test_query_change_uses_a_new_since_cursor():
    db = _db()
    repo = CursorRepository(db)
    old = "(국회 OR 대통령) lang:ko -is:retweet"
    new = "(국회) lang:ko -is:retweet"
    old_key = topic_query_cursor_key("politics", "korea", old)
    new_key = topic_query_cursor_key("politics", "korea", new)
    repo.set("x", old_key, "999")
    assert old_key != new_key
    assert repo.get("x", new_key) is None
    assert repo.get("x", old_key) == "999"


def test_same_external_id_is_stored_once():
    db = _db()
    now = datetime.utcnow()
    repo = RawItemRepository(db)
    item = RawItemDomain(
        provider=SourceType.X,
        external_id="post-1",
        text="a different sentence about the vote",
        fetched_at=now,
        published_at=now,
        raw_payload={},
    )
    assert repo.upsert_many([item]) == 1
    assert repo.upsert_many([item]) == 0
    assert db.query(RawItem).count() == 1


def test_dynamic_ttl_cap_and_dedupe():
    db = _db()
    repo = CursorRepository(db)
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    assert arm_dynamic_topic(
        repo,
        topic="Blackwell demand",
        industry="ai",
        source_lane="global",
        now=now,
    )
    assert (
        arm_dynamic_topic(
            repo,
            topic="Blackwell demand",
            industry="ai",
            source_lane="global",
            now=now,
        )
        is False
    )
    for index in range(5):
        arm_dynamic_topic(
            repo,
            topic=f"topic {index} extra",
            industry="ai",
            source_lane="global",
            now=now,
        )
    live = active_dynamic_queries(repo, now=now, limit=4)
    assert len(live) == 4
    later = now + timedelta(hours=13)
    assert active_dynamic_queries(repo, now=later, limit=4) == []
    remember_topics(repo, ["Blackwell demand surge", "x"])
    legacy = dynamic_search_queries(repo, budget=2)
    assert any("lang:en" in query for query in legacy)
    assert all("has:replies" not in query for query in legacy)


def test_dynamic_settle_ends_after_quiet_scans():
    db = _db()
    repo = CursorRepository(db)
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    arm_dynamic_topic(
        repo,
        topic="rate decision",
        industry="economy",
        source_lane="korea",
        now=now,
    )
    rows = active_dynamic_queries(repo, now=now)
    rows[0]["polled"] = True
    from app.pipeline.dynamic_query import _save_rows

    _save_rows(repo, rows)
    settle_dynamic_polls(repo, meaningful=set(), idle_limit=1, now=now)
    assert active_dynamic_queries(repo, now=now) == []


def test_daily_budget_stops_more_search():
    db = _db()
    repo = CursorRepository(db)
    now = datetime.now(timezone.utc)
    repo.set("x", "schedule:posts_kst", f"{kst_day(now)}|400")
    assert posts_fetched_today(repo, now) == 400
    assert _stop_for_daily_budget(repo, 400) is True
    assert _stop_for_daily_budget(repo, 0) is False
    assert set(ISSUE_INDUSTRY_KEYS)
