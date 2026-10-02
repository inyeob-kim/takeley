"""One-shot: print NEWS publish timing (KST)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.db.models import Signal
from app.db.session import SessionLocal

KST = ZoneInfo("Asia/Seoul")


def _kst(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


def main() -> None:
    s = get_settings()
    print("news_publish_interval_seconds", s.news_publish_interval_seconds)
    print("news_max_publish_per_cycle", s.news_max_publish_per_cycle)
    print("news_auto_publish", s.news_auto_publish)
    print("ingest_interval_seconds", s.ingest_interval_seconds)

    db = SessionLocal()
    rows = (
        db.query(Signal)
        .filter(
            Signal.content_kind == "NEWS",
            Signal.status == "published",
            Signal.published_at.isnot(None),
        )
        .order_by(Signal.published_at.desc())
        .limit(20)
        .all()
    )
    print("--- latest published NEWS (KST) ---")
    prev = None
    for r in rows:
        t = _kst(r.published_at)
        assert t is not None
        delta = None
        if prev is not None:
            delta = int((prev - t).total_seconds() / 60)
        gap = f"(+{delta}m from newer)" if delta is not None else ""
        print(t.strftime("%Y-%m-%d %H:%M"), gap, "|", (r.title or "")[:36])
        prev = t

    queued = (
        db.query(Signal)
        .filter(
            Signal.content_kind == "NEWS",
            Signal.status == "draft",
            Signal.scheduled_publish_at.isnot(None),
        )
        .order_by(Signal.scheduled_publish_at.asc())
        .limit(10)
        .all()
    )
    print("--- queued drip (KST) ---")
    for r in queued:
        t = _kst(r.scheduled_publish_at)
        assert t is not None
        print(t.strftime("%Y-%m-%d %H:%M"), "|", (r.title or "")[:36])

    day = datetime.now(tz=KST).replace(hour=0, minute=0, second=0, microsecond=0)
    day_utc = day.astimezone(timezone.utc).replace(tzinfo=None)
    today = (
        db.query(Signal)
        .filter(
            Signal.content_kind == "NEWS",
            Signal.status == "published",
            Signal.published_at >= day_utc,
        )
        .all()
    )
    hours = Counter(_kst(r.published_at).hour for r in today if r.published_at)
    print("--- today publish hours KST ---")
    for h in sorted(hours):
        print(f"{h:02d}:xx -> {hours[h]}")
    print("today count", len(today))
    db.close()


if __name__ == "__main__":
    main()
