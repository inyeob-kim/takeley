"""NEWS auto-publish / draft guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Signal
from app.pipeline.news_generate import NewsCard
from app.pipeline.normalize import content_fingerprint


@dataclass
class NewsGuardResult:
    accepted: bool
    reason: str = ""


def news_passes_guardrails(
    db: Session,
    *,
    card: NewsCard,
    source_url: str | None,
    provider: str | None,
    published_at: datetime | None,
    cluster_text: str,
) -> NewsGuardResult:
    settings = get_settings()
    if not card.ok:
        return NewsGuardResult(False, card.reason or "generate_failed")
    title = (card.title or "").strip()
    summary = (card.summary or "").strip()
    if len(title) < 4:
        return NewsGuardResult(False, "title_too_short")
    if len(summary) < 8:
        return NewsGuardResult(False, "summary_too_short")
    url = (source_url or "").strip()
    if not url:
        return NewsGuardResult(False, "missing_source_url")
    if not (provider or "").strip():
        return NewsGuardResult(False, "missing_provider")

    if published_at is None:
        return NewsGuardResult(False, "missing_published_at")
    max_age = timedelta(hours=max(1, int(settings.news_max_age_hours)))
    # Naive UTC compare (pipeline stores naive UTC).
    now = datetime.utcnow()
    pub = published_at
    if pub.tzinfo is not None:
        pub = pub.replace(tzinfo=None)
    if pub > now + timedelta(hours=1):
        return NewsGuardResult(False, "published_at_future")
    if now - pub > max_age:
        return NewsGuardResult(False, "too_old")

    # Near-dup vs recent NEWS/ISSUE titles (cheap fingerprint on title+summary).
    fp = content_fingerprint(f"{title}. {summary}")
    since = now - timedelta(days=5)
    recent = (
        db.query(Signal)
        .filter(
            Signal.status.in_(("draft", "published")),
            Signal.first_seen_at >= since,
        )
        .order_by(Signal.first_seen_at.desc())
        .limit(80)
        .all()
    )
    for row in recent:
        other = content_fingerprint(f"{row.title or ''}. {row.summary or ''}")
        if other and fp and other == fp:
            return NewsGuardResult(False, "duplicate_fingerprint")
        # Soft title equality
        if (row.title or "").strip() == title:
            return NewsGuardResult(False, "duplicate_title")

    # URL already attached as a source on an existing card
    from app.db.models import SignalSource

    hit = (
        db.query(SignalSource)
        .filter(SignalSource.url == url)
        .limit(1)
        .first()
    )
    if hit:
        return NewsGuardResult(False, "duplicate_source_url")

    _ = cluster_text  # reserved for future semantic dup
    return NewsGuardResult(True, "ok")


def count_news_cards_today(db: Session) -> int:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Signal)
        .filter(
            Signal.content_kind == "NEWS",
            Signal.status.in_(("draft", "published")),
            Signal.first_seen_at >= start,
        )
        .count()
    )
