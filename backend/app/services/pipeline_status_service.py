"""Read-only pipeline activity for UI (DB only — no external fetch)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import RawItem, Signal
from app.db.repositories import CursorRepository

def _active_fetch_window_seconds() -> float:
    """How long after a fetch to show the home collecting bar.

    Must stay shorter than the effective ingest interval — otherwise fast-ingest
    (e.g. TEST_FAST_INGEST=60s) keeps the bar permanently on.
    """
    from app.core.config import get_settings

    settings = get_settings()
    interval = min(
        settings.x_topic_search_interval_seconds,
        settings.x_accounts_interval_seconds,
        settings.rss_interval_seconds,
        settings.ingest_interval_seconds or settings.x_topic_search_interval_seconds,
    )
    # Brief pulse after each fetch; never cover the whole interval.
    return max(8.0, min(25.0, float(interval) * 0.25))


def pipeline_status(db: Session) -> dict:
    unprocessed = db.query(RawItem).filter(RawItem.processed == 0).count()
    published = db.query(Signal).filter(Signal.status == "published").count()
    draft = db.query(Signal).filter(Signal.status == "draft").count()

    cursor = CursorRepository(db)
    last_topic = cursor.get("x", "topic:last_fetch_at")
    last_accounts = cursor.get("x", "accounts:last_fetch_at")
    last_rss = cursor.get("news", "rss:last_fetch_at")

    ages: list[float] = []
    now = datetime.now(timezone.utc)
    for raw in (last_topic, last_accounts, last_rss):
        if not raw:
            continue
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ages.append((now - ts).total_seconds())
        except ValueError:
            continue

    window = _active_fetch_window_seconds()
    actively_fetching = any(a < window for a in ages)

    # Home "모으는 중":
    # - Feed already has published cards → brief pulse only after a recent fetch
    # - Drafts waiting for admin → never look like endless fetch
    # - Cold start (nothing yet) → unprocessed backlog or recent fetch
    if published > 0:
        collecting = actively_fetching
    elif draft > 0:
        collecting = False
    else:
        collecting = unprocessed > 0 or actively_fetching

    return {
        "collecting": collecting,
        "unprocessed_raw": int(unprocessed),
        "published_issues": int(published),
        "draft_issues": int(draft),
        "last_topic_fetch_at": last_topic,
        "last_accounts_fetch_at": last_accounts,
        "last_rss_fetch_at": last_rss,
        "message": (
            "소식을 모으고 있어요"
            if collecting
            else "최신 이슈를 확인할 수 있어요"
        ),
    }
