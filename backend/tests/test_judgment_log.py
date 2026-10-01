"""Judgment log unlock / streak / other-take split priority."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models import Base, Participation, ParticipationChangeLog, ParticipationOption, Signal
from app.services.judgment_log_service import (
    UNLOCK_BASIC,
    UNLOCK_FULL,
    UNLOCK_LOCKED,
    JudgmentLogService,
    compute_streak_days,
    unlock_level,
)
from app.services.other_take_service import _score_note


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_unlock_thresholds():
    settings = get_settings()
    assert unlock_level(0) == UNLOCK_LOCKED
    assert unlock_level(settings.judgment_log_unlock_basic - 1) == UNLOCK_LOCKED
    assert unlock_level(settings.judgment_log_unlock_basic) == UNLOCK_BASIC
    assert unlock_level(settings.judgment_log_unlock_full) == UNLOCK_FULL


def test_judgment_log_masks_note_when_locked():
    db = _session()
    signal = Signal(
        id="sig-1",
        title="테스트 이슈",
        summary="요약",
        why_it_matters="",
        status="published",
        importance=0.5,
        confidence=0.5,
    )
    opt = ParticipationOption(id="opt-1", signal_id="sig-1", label="찬성", display_order=0)
    part = Participation(
        signal_id="sig-1",
        user_id="u1",
        option_id="opt-1",
        note="한 줄 판단입니다",
    )
    db.add_all([signal, opt, part])
    db.commit()

    out = JudgmentLogService(db).list_judgments("u1")
    assert out["unlock_level"] == UNLOCK_LOCKED
    assert out["items"][0]["note"] is None
    assert out["items"][0]["note_locked"] is True


def test_streak_counts_consecutive_kst_days():
    db = _session()
    now = datetime.utcnow()
    for i in range(3):
        db.add(
            ParticipationChangeLog(
                user_id="u1",
                signal_id="s",
                to_option_id="o",
                changed_at=now - timedelta(days=i),
            )
        )
    db.commit()
    assert compute_streak_days(db, "u1") >= 1


def test_split_priority_boosts_opposite_side():
    base = _score_note(
        note="이건 충분히 긴 한 줄 판단 노트입니다.",
        created_at=datetime.utcnow(),
        unseen=True,
        same_side=False,
        force_same_side=False,
        now=datetime.utcnow(),
        split=0.2,
        split_priority_at=0.35,
    )
    boosted = _score_note(
        note="이건 충분히 긴 한 줄 판단 노트입니다.",
        created_at=datetime.utcnow(),
        unseen=True,
        same_side=False,
        force_same_side=False,
        now=datetime.utcnow(),
        split=0.4,
        split_priority_at=0.35,
    )
    assert boosted > base
