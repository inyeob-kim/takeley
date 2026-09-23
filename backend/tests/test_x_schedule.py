"""X scan slots, since_id advance, and industry-reserved LLM pool."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.repositories import CursorRepository
from app.db.session import Base
from app.pipeline.candidate import ScoredCandidate, rank_for_pool_reserved
from app.services.x_ingest_admin import parse_track_accounts
from app.pipeline.x_schedule import (
    advance_since_id,
    allow_extra_page,
    arm_hot_topic,
    build_fetch_plan,
    due_slot,
    lanes_for_scan,
    note_hot_result,
    remember_hot_polls,
    settle_hot_polls,
    weaker_source_lane,
)


def test_parse_track_accounts_strips_at_and_dupes():
    assert parse_track_accounts(" @DeItaone, StockMKTNewz,deitaone ") == [
        "DeItaone",
        "StockMKTNewz",
    ]


def test_parse_track_accounts_rejects_bad_handles():
    with pytest.raises(ValueError):
        parse_track_accounts("not a handle")


def test_due_slot_fires_once_inside_window():
    now = datetime(2026, 9, 24, 21, 35, tzinfo=timezone.utc)  # 06:35 KST on the 25th
    slot = due_slot(now, "06:30,16:00,22:30", window_minutes=40, last_slot_key=None)
    assert slot is not None
    assert slot.label == "morning"
    assert slot.key == "2026-09-25T06:30"
    again = due_slot(
        now, "06:30,16:00,22:30", window_minutes=40, last_slot_key=slot.key
    )
    assert again is None


def test_due_slot_misses_outside_window():
    now = datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)  # 09:00 KST
    assert (
        due_slot(now, "06:30,16:00,22:30", window_minutes=40, last_slot_key=None)
        is None
    )


def test_lanes_for_scan_keeps_one_language():
    lanes = lanes_for_scan(
        "politics,economy,ai",
        "korea",
        limit=10,
    )
    assert [lane.industry_key for lane in lanes] == ["politics", "economy", "ai"]
    assert {lane.source_lane for lane in lanes} == {"korea"}


def test_advance_since_id_keeps_oldest_when_page_is_full():
    nxt = advance_since_id(
        ["300", "100", "200"],
        previous="50",
        page_cap=3,
    )
    assert nxt == "100"


def test_advance_since_id_jumps_to_newest_when_caught_up():
    nxt = advance_since_id(["300", "100"], previous="50", page_cap=3)
    assert nxt == "300"


def test_rank_reserves_one_slot_per_industry():
    def candidate(raw_id: str, industry: str, score: float) -> ScoredCandidate:
        return ScoredCandidate(
            raw_id=raw_id,
            text="text " * 8,
            url=None,
            provider="x",
            published_at=None,
            payload={"issue_industry": industry},
            priority_score=score,
        )

    pool = rank_for_pool_reserved(
        [
            candidate("a1", "ai", 0.9),
            candidate("a2", "ai", 0.8),
            candidate("c1", "culture", 0.2),
        ],
        budget=2,
    )
    assert {item.raw_id for item in pool} == {"a1", "c1"}


def _cursors():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    return CursorRepository(db)


def test_weaker_lane_picks_fewer_analyzed_posts():
    assert weaker_source_lane(2, 9, afternoon="global") == "korea"
    assert weaker_source_lane(9, 2, afternoon="korea") == "global"


def test_weaker_lane_tie_uses_the_other_afternoon_lane():
    assert weaker_source_lane(4, 4, afternoon="global") == "korea"
    assert weaker_source_lane(4, 4, afternoon="korea") == "global"


def test_hot_clears_after_two_quiet_meaningful_polls():
    repo = _cursors()
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    arm_hot_topic(
        repo,
        industry_key="ai",
        source_lane="global",
        now_utc=now,
        max_hours=6,
    )
    note_hot_result(
        repo,
        industry_key="ai",
        source_lane="global",
        meaningful=False,
        idle_limit=2,
    )
    assert repo.get("x", "hot:ai:global") is not None
    note_hot_result(
        repo,
        industry_key="ai",
        source_lane="global",
        meaningful=True,
        idle_limit=2,
    )
    remember_hot_polls(repo, ["ai:global"])
    settle_hot_polls(repo, meaningful=set(), idle_limit=2)
    assert repo.get("x", "hot:ai:global") is not None
    remember_hot_polls(repo, ["ai:global"])
    settle_hot_polls(repo, meaningful=set(), idle_limit=2)
    assert repo.get("x", "hot:ai:global") is None


def test_extra_page_only_when_hot_and_page_is_full():
    assert allow_extra_page(mode="hot", page_full=True) is True
    assert allow_extra_page(mode="hot", page_full=False) is False
    assert allow_extra_page(mode="normal", page_full=True) is False


def test_settle_hot_polls_keeps_topic_when_issue_lands():
    repo = _cursors()
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    arm_hot_topic(
        repo,
        industry_key="politics",
        source_lane="korea",
        now_utc=now,
        max_hours=6,
    )
    remember_hot_polls(repo, ["politics:korea"])
    settle_hot_polls(repo, meaningful={"politics:korea"}, idle_limit=2)
    raw = repo.get("x", "hot:politics:korea")
    assert raw is not None
    assert raw.split("|")[1] == "0"


def test_morning_accounts_run_only_in_the_first_slot():
    config = SimpleNamespace(
        scan_mode="scheduled",
        scan_hours_kst="06:30,16:00,22:30",
        scan_window_minutes=40,
        morning_lane="korea",
        afternoon_lane="global",
        night_lane="korea",
        lanes_per_scan=1,
        max_results=10,
        industries="politics",
        accounts_on="morning",
        dynamic_mode="off",
        hot_enabled=False,
        hot_interval_minutes=45,
        hot_idle_scans=2,
        hot_max_hours=6,
        hot_reply_spike=15,
    )
    morning = datetime(2026, 9, 24, 21, 35, tzinfo=timezone.utc)
    afternoon = datetime(2026, 9, 25, 7, 5, tzinfo=timezone.utc)
    assert build_fetch_plan(config, _cursors(), morning).run_accounts is True
    assert build_fetch_plan(config, _cursors(), afternoon).run_accounts is False


def test_night_accounts_follow_the_last_listed_time():
    config = SimpleNamespace(
        scan_mode="scheduled",
        scan_hours_kst="06:30,22:30",
        scan_window_minutes=40,
        morning_lane="korea",
        afternoon_lane="global",
        night_lane="auto",
        lanes_per_scan=1,
        max_results=10,
        industries="politics",
        accounts_on="night",
        dynamic_mode="off",
        hot_enabled=False,
        hot_interval_minutes=45,
        hot_idle_scans=2,
        hot_max_hours=6,
        hot_reply_spike=15,
    )
    morning = datetime(2026, 9, 24, 21, 35, tzinfo=timezone.utc)
    late = datetime(2026, 9, 25, 13, 35, tzinfo=timezone.utc)
    assert build_fetch_plan(config, _cursors(), morning).run_accounts is False
    assert build_fetch_plan(config, _cursors(), late).run_accounts is True
