"""Cursor seed + lane since_id safety for Korea/Global topic ingest."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.repositories import CursorRepository
from app.pipeline.industries import (
    legacy_topic_since_cursor_key,
    topic_since_cursor_key,
)
from worker.jobs.ingest import _resolve_topic_since_id


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_resolve_topic_since_id_seeds_from_legacy_without_deleting():
    db = _session()
    repo = CursorRepository(db)
    legacy_key = legacy_topic_since_cursor_key("ai")
    lane_key = topic_since_cursor_key("ai", "global")
    repo.set("x", legacy_key, "12345")

    got = _resolve_topic_since_id(repo, industry_key="ai", source_lane="global")
    assert got == "12345"
    assert repo.get("x", lane_key) == "12345"
    # Legacy cursor must remain (never deleted/reset).
    assert repo.get("x", legacy_key) == "12345"

    # Second call uses lane cursor directly.
    repo.set("x", lane_key, "99999")
    assert (
        _resolve_topic_since_id(repo, industry_key="ai", source_lane="global")
        == "99999"
    )
    assert repo.get("x", legacy_key) == "12345"


def test_resolve_topic_since_id_korea_and_global_seed_independently():
    db = _session()
    repo = CursorRepository(db)
    repo.set("x", legacy_topic_since_cursor_key("tech"), "777")

    ko = _resolve_topic_since_id(repo, industry_key="tech", source_lane="korea")
    gl = _resolve_topic_since_id(repo, industry_key="tech", source_lane="global")
    assert ko == "777"
    assert gl == "777"
    assert repo.get("x", topic_since_cursor_key("tech", "korea")) == "777"
    assert repo.get("x", topic_since_cursor_key("tech", "global")) == "777"
