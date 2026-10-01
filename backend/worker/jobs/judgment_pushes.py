"""Mark old published Issues STALE and enqueue judgment-linked pushes."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import Signal
from app.services.push_enqueue_service import (
    enqueue_judgment_closure,
    enqueue_judgment_recap,
)

logger = logging.getLogger(__name__)

# Soft age before PUBLISHED/UPDATED → STALE (matches closures_me soft window).
_STALE_AFTER_DAYS = 14


def mark_stale_issues(db: Session, *, older_than_days: int = _STALE_AFTER_DAYS) -> dict:
    """Promote aged published Issues to lifecycle=STALE and enqueue closure pushes."""
    cutoff = datetime.utcnow() - timedelta(days=max(1, older_than_days))
    rows = (
        db.query(Signal)
        .filter(
            Signal.status == "published",
            Signal.published_at.isnot(None),
            Signal.published_at < cutoff,
            Signal.lifecycle.in_(("PUBLISHED", "UPDATED", "CANDIDATE")),
        )
        .limit(40)
        .all()
    )
    marked = 0
    pushed = 0
    for row in rows:
        row.lifecycle = "STALE"
        row.updated_at = datetime.utcnow()
        marked += 1
        try:
            result = enqueue_judgment_closure(
                db, signal_id=row.id, title=row.title
            )
            pushed += int(result.get("enqueued") or 0)
        except Exception:
            logger.exception("judgment_closure enqueue failed signal=%s", row.id)
    if marked:
        db.commit()
    logger.info("mark_stale_issues marked=%s closure_enqueued=%s", marked, pushed)
    return {"marked": marked, "closure_enqueued": pushed}


def run_judgment_pushes(db: Session) -> dict:
    """Heavy-cycle hook: stale mark + daily recap enqueue."""
    stale = mark_stale_issues(db)
    recap = enqueue_judgment_recap(db)
    return {"stale": stale, "recap": recap}
