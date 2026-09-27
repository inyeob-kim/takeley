"""RSS-only unprocessed expiry. X raw_items keep existing process policy."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import RawItem

RSS_PAYLOAD_SOURCE = "rss_feed"
RSS_STALE_HOURS = 72


def expire_stale_rss_items(
    db: Session,
    *,
    now: datetime | None = None,
    max_age_hours: int = RSS_STALE_HOURS,
) -> int:
    """Mark old unprocessed RSS rows processed so they cannot flood LLM budget."""
    cutoff = (now or datetime.utcnow()) - timedelta(hours=max_age_hours)
    rows = (
        db.query(RawItem)
        .filter(
            RawItem.processed == 0,
            RawItem.provider == "news",
            RawItem.fetched_at < cutoff,
        )
        .all()
    )
    expired = 0
    for row in rows:
        payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        if payload.get("source") != RSS_PAYLOAD_SOURCE:
            continue
        row.processed = 1
        expired += 1
    if expired:
        db.commit()
    return expired
