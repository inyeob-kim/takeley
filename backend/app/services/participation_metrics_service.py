"""Admin participation funnel / A-B metrics (Phase 6 MVP)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    IssueUserEvent,
    OtherTakeExposure,
    Participation,
    UserPreference,
)


def participation_metrics(db: Session, *, days: int = 7) -> dict:
    since = datetime.utcnow() - timedelta(days=max(1, min(days, 30)))

    bucket_rows = (
        db.query(UserPreference.participation_experiment_bucket, func.count())
        .filter(UserPreference.participation_experiment_bucket.in_(("A", "B")))
        .group_by(UserPreference.participation_experiment_bucket)
        .all()
    )
    buckets = {"A": 0, "B": 0}
    for bucket, n in bucket_rows:
        key = (bucket or "").upper()
        if key in buckets:
            buckets[key] = int(n)

    event_rows = (
        db.query(IssueUserEvent.event, func.count())
        .filter(
            IssueUserEvent.created_at >= since,
            IssueUserEvent.event.in_(
                (
                    "vote",
                    "position_selected",
                    "position_changed",
                    "take_submitted",
                    "distribution_viewed",
                    "other_take_exposed",
                    "other_take_skipped",
                    "other_take_opened",
                    "recap_viewed",
                )
            ),
        )
        .group_by(IssueUserEvent.event)
        .all()
    )
    events = {e: int(n) for e, n in event_rows}

    notes = (
        db.query(func.count())
        .select_from(Participation)
        .filter(
            Participation.updated_at >= since,
            Participation.note.isnot(None),
            Participation.note != "",
        )
        .scalar()
    )
    votes = (
        db.query(func.count())
        .select_from(Participation)
        .filter(Participation.created_at >= since)
        .scalar()
    )
    other_exposures = (
        db.query(func.count())
        .select_from(OtherTakeExposure)
        .filter(OtherTakeExposure.exposed_at >= since)
        .scalar()
    )

    return {
        "days": days,
        "since": since.isoformat() + "Z",
        "buckets": buckets,
        "events": events,
        "participations_created": int(votes or 0),
        "notes_written": int(notes or 0),
        "other_take_exposures": int(other_exposures or 0),
    }
