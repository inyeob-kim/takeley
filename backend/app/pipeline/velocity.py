"""Engagement velocity from metric snapshots (external signal only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MetricSnapshot


@dataclass(frozen=True)
class VelocityReading:
    reply_velocity: float  # replies per hour
    engagement_velocity: float
    trend_status: str  # NORMAL | RISING | TRENDING (external bucket only)


def latest_snapshots(
    db: Session, signal_id: str, *, limit: int = 2
) -> list[MetricSnapshot]:
    rows = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.signal_id == signal_id)
        .order_by(MetricSnapshot.captured_at.desc())
        .limit(max(1, limit))
        .all()
    )
    rows.reverse()
    return rows


def snapshot_has_activity(snap: MetricSnapshot) -> bool:
    """Any observable external engagement — replies are NOT required."""
    return (
        int(snap.reply_count or 0) > 0
        or int(snap.like_count or 0) > 0
        or int(snap.retweet_count or 0) > 0
        or int(snap.quote_count or 0) > 0
        or float(snap.engagement_score or 0.0) > 0.0
    )


def snapshots_show_activity_delta(older: MetricSnapshot, newer: MetricSnapshot) -> bool:
    """Positive change between snapshots (replies or engagement components)."""
    return (
        int(newer.reply_count or 0) > int(older.reply_count or 0)
        or int(newer.like_count or 0) > int(older.like_count or 0)
        or int(newer.retweet_count or 0) > int(older.retweet_count or 0)
        or int(newer.quote_count or 0) > int(older.quote_count or 0)
        or float(newer.engagement_score or 0.0) > float(older.engagement_score or 0.0)
    )


def record_metric_snapshot(
    db: Session,
    *,
    signal_id: str,
    reply_count: int,
    like_count: int = 0,
    retweet_count: int = 0,
    quote_count: int = 0,
) -> MetricSnapshot:
    eng = (
        float(like_count)
        + float(reply_count) * 3.0
        + float(retweet_count) * 2.0
        + float(quote_count) * 2.5
    )
    row = MetricSnapshot(
        signal_id=signal_id,
        reply_count=int(reply_count),
        like_count=int(like_count),
        retweet_count=int(retweet_count),
        quote_count=int(quote_count),
        engagement_score=eng,
        captured_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    return row


def compute_velocity(db: Session, signal_id: str) -> VelocityReading:
    settings = get_settings()
    rows = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.signal_id == signal_id)
        .order_by(MetricSnapshot.captured_at.asc())
        .all()
    )
    if len(rows) < 2:
        return VelocityReading(0.0, 0.0, "NORMAL")
    a, b = rows[-2], rows[-1]
    dt_h = max(
        1.0 / 60.0,
        (b.captured_at - a.captured_at).total_seconds() / 3600.0,
    )
    reply_v = (b.reply_count - a.reply_count) / dt_h
    eng_v = (b.engagement_score - a.engagement_score) / dt_h
    if (
        reply_v >= float(settings.issue_trending_reply_velocity)
        or eng_v >= float(settings.issue_trending_engagement_velocity)
    ):
        status = "TRENDING"
    elif (
        reply_v >= float(settings.issue_rising_reply_velocity)
        or eng_v >= float(settings.issue_rising_engagement_velocity)
    ):
        status = "RISING"
    else:
        status = "NORMAL"
    return VelocityReading(reply_v, eng_v, status)
