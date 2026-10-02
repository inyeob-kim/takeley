"""One-shot: check ISSUE/NEWS publish health on prod."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.db.models import RawItem, Signal
from app.db.session import SessionLocal

KST = ZoneInfo("Asia/Seoul")


def kst(dt: datetime | None) -> str:
    if not dt:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")


def main() -> None:
    s = get_settings()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    h6 = now - timedelta(hours=6)
    h24 = now - timedelta(hours=24)

    print("=== config ===")
    print("news_pipeline_enabled", s.news_pipeline_enabled)
    print("news_auto_publish", s.news_auto_publish)
    print("news_publish_interval_s", s.news_publish_interval_seconds)
    print("news_max_publish_per_cycle", s.news_max_publish_per_cycle)
    print("daily_news_cap", s.daily_news_cap)
    print("daily_signal_cap", s.daily_signal_cap)
    print("ingest_interval_s", s.ingest_interval_seconds)
    print("now_kst", kst(now))

    db = SessionLocal()

    def count(kind: str | None, status: str | None = None, since=None, field="published_at"):
        q = db.query(Signal)
        if kind:
            q = q.filter(Signal.content_kind == kind)
        if status:
            q = q.filter(Signal.status == status)
        if since is not None:
            q = q.filter(getattr(Signal, field) >= since)
        return q.count()

    print("\n=== counts ===")
    for kind in ("ISSUE", "NEWS"):
        print(
            kind,
            "published_total",
            count(kind, "published"),
            "draft",
            count(kind, "draft"),
            "today_pub",
            count(kind, "published", day, "published_at"),
            "6h_pub",
            count(kind, "published", h6, "published_at"),
            "24h_pub",
            count(kind, "published", h24, "published_at"),
            "today_created",
            count(kind, None, day, "first_seen_at"),
        )

    print("\n=== latest ISSUE published ===")
    for r in (
        db.query(Signal)
        .filter(Signal.content_kind == "ISSUE", Signal.status == "published")
        .order_by(Signal.published_at.desc())
        .limit(8)
        .all()
    ):
        print(kst(r.published_at), "|", (r.title or "")[:48])

    print("\n=== latest NEWS published ===")
    for r in (
        db.query(Signal)
        .filter(Signal.content_kind == "NEWS", Signal.status == "published")
        .order_by(Signal.published_at.desc())
        .limit(8)
        .all()
    ):
        print(kst(r.published_at), "|", (r.title or "")[:48])

    print("\n=== NEWS drip queue (draft+scheduled) ===")
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
    if not queued:
        print("(empty)")
    for r in queued:
        due = r.scheduled_publish_at
        overdue = due and due <= now
        print(
            kst(due),
            "OVERDUE" if overdue else "queued",
            "|",
            (r.title or "")[:40],
        )

    print("\n=== ISSUE drafts with schedule ===")
    iq = (
        db.query(Signal)
        .filter(
            Signal.content_kind == "ISSUE",
            Signal.status == "draft",
            Signal.scheduled_publish_at.isnot(None),
        )
        .order_by(Signal.scheduled_publish_at.asc())
        .limit(8)
        .all()
    )
    if not iq:
        print("(empty)")
    for r in iq:
        print(kst(r.scheduled_publish_at), "|", (r.title or "")[:40])

    print("\n=== ISSUE drafts (unscheduled, recent) ===")
    drafts = (
        db.query(Signal)
        .filter(Signal.content_kind == "ISSUE", Signal.status == "draft")
        .order_by(Signal.first_seen_at.desc())
        .limit(8)
        .all()
    )
    if not drafts:
        print("(empty)")
    for r in drafts:
        print(
            "seen",
            kst(r.first_seen_at),
            "sched",
            kst(r.scheduled_publish_at),
            "|",
            (r.title or "")[:40],
        )

    print("\n=== raw pipeline backlog ===")
    unprocessed = db.query(RawItem).filter(RawItem.processed_at.is_(None)).count()
    recent_raw = (
        db.query(RawItem)
        .filter(RawItem.fetched_at >= h6)
        .count()
        if hasattr(RawItem, "fetched_at")
        else None
    )
    # fetched_at may not exist — try created_at / first_seen
    print("unprocessed_raw", unprocessed)
    for col in ("fetched_at", "created_at", "inserted_at"):
        if hasattr(RawItem, col):
            n = db.query(RawItem).filter(getattr(RawItem, col) >= h6).count()
            print(f"raw_last_6h_by_{col}", n)

    overdue_news = (
        db.query(Signal)
        .filter(
            Signal.content_kind == "NEWS",
            Signal.status == "draft",
            Signal.scheduled_publish_at.isnot(None),
            Signal.scheduled_publish_at <= now,
        )
        .count()
    )
    print("\n=== health flags ===")
    print("overdue_news_drafts", overdue_news)
    last_issue = (
        db.query(Signal.published_at)
        .filter(Signal.content_kind == "ISSUE", Signal.status == "published")
        .order_by(Signal.published_at.desc())
        .limit(1)
        .scalar()
    )
    last_news = (
        db.query(Signal.published_at)
        .filter(Signal.content_kind == "NEWS", Signal.status == "published")
        .order_by(Signal.published_at.desc())
        .limit(1)
        .scalar()
    )
    print("last_issue_pub_kst", kst(last_issue))
    print("last_news_pub_kst", kst(last_news))
    if last_issue:
        print("hours_since_issue", round((now - last_issue).total_seconds() / 3600, 1))
    if last_news:
        print("hours_since_news", round((now - last_news).total_seconds() / 3600, 1))

    db.close()


if __name__ == "__main__":
    main()
