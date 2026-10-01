"""Other-person judgment note exposure — deterministic gates + scoring."""

from __future__ import annotations

import hashlib
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    OtherTakeExposure,
    Participation,
    ParticipationOption,
    UserPreference,
)
from app.services.content_moderation import contains_objectionable
from app.services.issue_service import _append_user_event, _option_counts

logger = logging.getLogger(__name__)

TARGET_PARTICIPATION = "participation"


@dataclass
class OtherTakeCandidate:
    participation_id: str
    author_id: str
    option_id: str
    option_label: str
    note: str
    same_side: bool
    score: float


def _session_key(user_id: str, *, now: datetime, idle_minutes: int) -> str:
    """Bucket by idle window: floor(epoch / idle_seconds) changes after idle gap approx."""
    idle = max(60, idle_minutes * 60)
    bucket = int(now.timestamp()) // idle
    return f"{user_id}:{bucket}"


def _ensure_bucket(db: Session, user_id: str) -> str:
    prefs = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if prefs is None:
        prefs = UserPreference(user_id=user_id)
        db.add(prefs)
        db.flush()
    bucket = (prefs.participation_experiment_bucket or "").strip().upper()
    if bucket in ("A", "B"):
        return bucket
    # Sticky ~50/50 from user_id hash.
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    bucket = "A" if int(digest[:8], 16) % 2 == 0 else "B"
    prefs.participation_experiment_bucket = bucket
    prefs.updated_at = datetime.utcnow()
    db.commit()
    return bucket


def compute_split(counts: dict[str, int], my_option_id: str) -> float:
    """split = 1 - max(mine, others) / (mine + others) using my option vs rest."""
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    mine = float(counts.get(my_option_id, 0))
    others = float(total - mine)
    if mine + others <= 0:
        return 0.0
    return 1.0 - (max(mine, others) / (mine + others))


def _skip_rate_7d(db: Session, user_id: str, *, now: datetime) -> float:
    since = now - timedelta(days=7)
    rows = (
        db.query(OtherTakeExposure)
        .filter(
            OtherTakeExposure.user_id == user_id,
            OtherTakeExposure.exposed_at >= since,
        )
        .all()
    )
    if not rows:
        return 0.0
    skipped = sum(1 for r in rows if r.skipped_at is not None)
    return skipped / len(rows)


def _exposures_today(db: Session, user_id: str, *, now: datetime) -> int:
    start = datetime(now.year, now.month, now.day)
    return (
        db.query(OtherTakeExposure)
        .filter(
            OtherTakeExposure.user_id == user_id,
            OtherTakeExposure.exposed_at >= start,
        )
        .count()
    )


def _session_already_exposed(
    db: Session, user_id: str, session_key: str
) -> bool:
    return (
        db.query(OtherTakeExposure)
        .filter(
            OtherTakeExposure.user_id == user_id,
            OtherTakeExposure.session_key == session_key,
        )
        .first()
        is not None
    )


def _authors_exposed_today(
    db: Session, user_id: str, *, now: datetime
) -> set[str]:
    start = datetime(now.year, now.month, now.day)
    rows = (
        db.query(OtherTakeExposure.author_id)
        .filter(
            OtherTakeExposure.user_id == user_id,
            OtherTakeExposure.exposed_at >= start,
        )
        .all()
    )
    return {r[0] for r in rows if r[0]}


def _seen_target_ids(
    db: Session, user_id: str, signal_id: str
) -> set[str]:
    rows = (
        db.query(OtherTakeExposure.target_id)
        .filter(
            OtherTakeExposure.user_id == user_id,
            OtherTakeExposure.signal_id == signal_id,
            OtherTakeExposure.target_type == TARGET_PARTICIPATION,
        )
        .all()
    )
    return {r[0] for r in rows if r[0]}


def _score_note(
    *,
    note: str,
    created_at: datetime | None,
    unseen: bool,
    same_side: bool,
    force_same_side: bool,
    now: datetime,
    split: float = 0.0,
    split_priority_at: float = 0.35,
) -> float:
    score = 0.0
    n = len(note)
    if 40 <= n <= 80:
        score += 3.0
    elif n < 40:
        score += 1.0
    else:
        score -= 1.5
    if unseen:
        score += 2.0
    if created_at:
        age_h = max(0.0, (now - created_at).total_seconds() / 3600.0)
        score += max(0.0, 2.0 - age_h / 24.0)
    if force_same_side:
        score += 4.0 if same_side else -5.0
    elif not same_side:
        score += 1.0
        # When debate is sharp, prefer opposite-side discovery slightly more.
        if split >= float(split_priority_at):
            score += 1.5
    return score


def pick_other_take(
    db: Session,
    *,
    issue_id: str,
    user_id: str,
) -> dict | None:
    """Return other-take card dict or None if gated out / no candidate."""
    settings = get_settings()
    now = datetime.utcnow()
    bucket = _ensure_bucket(db, user_id)
    if bucket == "A":
        return None

    mine = (
        db.query(Participation)
        .filter(
            Participation.signal_id == issue_id,
            Participation.user_id == user_id,
        )
        .first()
    )
    if mine is None:
        return None

    counts = _option_counts(db, issue_id)
    total = sum(counts.values())
    min_n = max(1, int(settings.other_take_min_responses))
    if total < min_n:
        return None

    split = compute_split(counts, mine.option_id)
    if split < float(settings.other_take_split_hide_below):
        return None

    idle = int(settings.other_take_session_idle_minutes)
    session_key = _session_key(user_id, now=now, idle_minutes=idle)
    if _session_already_exposed(db, user_id, session_key):
        return None

    if _exposures_today(db, user_id, now=now) >= int(settings.other_take_daily_cap):
        return None

    if _skip_rate_7d(db, user_id, now=now) >= float(
        settings.other_take_skip_rate_block
    ):
        return None

    seen = _seen_target_ids(db, user_id, issue_id)
    authors_today = _authors_exposed_today(db, user_id, now=now)
    exposure_n = _exposures_today(db, user_id, now=now)
    every_n = max(1, int(settings.other_take_same_side_every_n))
    force_same_side = (exposure_n + 1) % every_n == 0

    labels = {
        o.id: o.label
        for o in db.query(ParticipationOption)
        .filter(ParticipationOption.signal_id == issue_id)
        .all()
    }

    rows = (
        db.query(Participation)
        .filter(
            Participation.signal_id == issue_id,
            Participation.user_id != user_id,
            Participation.note.isnot(None),
        )
        .all()
    )
    candidates: list[OtherTakeCandidate] = []
    for row in rows:
        note = (row.note or "").strip()
        if len(note) < 8:
            continue
        if contains_objectionable(note):
            continue
        if row.id in seen:
            continue
        if row.user_id in authors_today:
            continue
        same_side = row.option_id == mine.option_id
        score = _score_note(
            note=note,
            created_at=row.created_at,
            unseen=True,
            same_side=same_side,
            force_same_side=force_same_side,
            now=now,
            split=split,
            split_priority_at=float(settings.other_take_split_priority_at),
        )
        if force_same_side and not same_side:
            continue
        candidates.append(
            OtherTakeCandidate(
                participation_id=row.id,
                author_id=row.user_id,
                option_id=row.option_id,
                option_label=labels.get(row.option_id) or "",
                note=note,
                same_side=same_side,
                score=score,
            )
        )

    if not candidates:
        return None

    best = max(c.score for c in candidates)
    top = [c for c in candidates if abs(c.score - best) < 1e-6]
    chosen = random.choice(top)

    exposure = OtherTakeExposure(
        user_id=user_id,
        signal_id=issue_id,
        target_type=TARGET_PARTICIPATION,
        target_id=chosen.participation_id,
        author_id=chosen.author_id,
        session_key=session_key,
        exposed_at=now,
    )
    db.add(exposure)
    _append_user_event(
        db, user_id=user_id, signal_id=issue_id, event="other_take_exposed"
    )
    db.commit()
    db.refresh(exposure)

    return {
        "exposure_id": exposure.id,
        "issue_id": issue_id,
        "target_type": TARGET_PARTICIPATION,
        "target_id": chosen.participation_id,
        "author_id": chosen.author_id,
        "option_label": chosen.option_label or None,
        "note": chosen.note,
        "same_side": chosen.same_side,
    }


def mark_other_take(
    db: Session,
    *,
    issue_id: str,
    user_id: str,
    action: str,
    exposure_id: str | None = None,
) -> bool:
    """action: skip | open. Returns True if updated."""
    now = datetime.utcnow()
    q = db.query(OtherTakeExposure).filter(
        OtherTakeExposure.user_id == user_id,
        OtherTakeExposure.signal_id == issue_id,
    )
    if exposure_id:
        q = q.filter(OtherTakeExposure.id == exposure_id)
    row = q.order_by(OtherTakeExposure.exposed_at.desc()).first()
    if row is None:
        return False
    if action == "skip":
        row.skipped_at = now
        event = "other_take_skipped"
    elif action == "open":
        row.opened_at = now
        event = "other_take_opened"
    else:
        return False
    _append_user_event(db, user_id=user_id, signal_id=issue_id, event=event)
    db.commit()
    return True
