"""Persist last-run stats onto discovery_modules. Does not change ingest logic."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import DiscoveryModule, PipelineControl, RssFeed
from app.discovery.protocol import ModuleRunResult

KNOWN_MODULE_IDS = (
    "x",
    "rss",
    "trends",
    "reddit",
    "hacker_news",
    "official",
)

DEFAULT_ENABLED = {"x": True}
DEFAULT_INTERVALS = {
    "rss": 3600,
    "trends": 3600,
    "reddit": 1800,
    "hacker_news": 1800,
    "official": 3600,
}
# Civic / world / KR wires. Empty rss_feeds made the ON switch a no-op.
DEFAULT_RSS_FEEDS = (
    {
        "name": "BBC News",
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
        "language": "en",
        "category": "world",
    },
    {
        "name": "Google News",
        "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "language": "en",
        "category": "world",
    },
    {
        "name": "연합뉴스TV",
        "url": "https://www.yonhapnewstv.co.kr/browse/feed/",
        "language": "ko",
        "category": "world",
    },
)
PIPELINE_ID = "default"


def _seed_default_rss_feeds(db: Session) -> bool:
    if db.query(RssFeed).first() is not None:
        return False
    for spec in DEFAULT_RSS_FEEDS:
        db.add(
            RssFeed(
                name=spec["name"],
                url=spec["url"],
                language=spec["language"],
                category=spec["category"],
                enabled=True,
            )
        )
    rss = db.query(DiscoveryModule).filter(DiscoveryModule.id == "rss").first()
    if rss is not None:
        # Fetch the new feeds on the next due tick, not after a leftover skip.
        rss.last_finished_at = None
        rss.last_started_at = None
        rss.last_status = None
    return True


def ensure_seeded(db: Session) -> None:
    existing = {row.id: row for row in db.query(DiscoveryModule).all()}
    dirty = False
    for module_id in KNOWN_MODULE_IDS:
        interval = DEFAULT_INTERVALS.get(module_id)
        row = existing.get(module_id)
        if row is None:
            db.add(
                DiscoveryModule(
                    id=module_id,
                    enabled=DEFAULT_ENABLED.get(module_id, False),
                    interval_seconds=interval,
                )
            )
            dirty = True
            continue
        if row.interval_seconds is None and interval:
            row.interval_seconds = interval
            dirty = True
    if db.query(PipelineControl).filter(PipelineControl.id == PIPELINE_ID).first() is None:
        db.add(PipelineControl(id=PIPELINE_ID))
        dirty = True
    if _seed_default_rss_feeds(db):
        dirty = True
    if dirty:
        db.commit()


def is_module_enabled(db: Session, module_id: str) -> bool:
    ensure_seeded(db)
    row = db.query(DiscoveryModule).filter(DiscoveryModule.id == module_id).first()
    return bool(row and row.enabled)


def should_run_module(db: Session, module_id: str) -> tuple[bool, str | None]:
    """Decide this tick only. A running module is never cancelled mid-flight."""
    if not is_module_enabled(db, module_id):
        return False, "disabled"
    row = db.query(DiscoveryModule).filter(DiscoveryModule.id == module_id).first()
    if row is None:
        return False, "unknown"
    interval = row.interval_seconds
    if not interval or interval <= 0:
        return True, None
    last = row.last_finished_at or row.last_started_at
    if last is None:
        return True, None
    age = (datetime.utcnow() - last).total_seconds()
    if age < interval:
        return False, "interval"
    return True, None


def get_pipeline_controls(db: Session) -> PipelineControl:
    ensure_seeded(db)
    row = db.query(PipelineControl).filter(PipelineControl.id == PIPELINE_ID).first()
    if row is None:
        row = PipelineControl(id=PIPELINE_ID)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def mark_module_started(db: Session, module_id: str, started_at: datetime) -> None:
    """Persist start before fetch so a hung Official/SEC run is visible."""
    ensure_seeded(db)
    row = db.query(DiscoveryModule).filter(DiscoveryModule.id == module_id).first()
    if row is None:
        return
    row.last_started_at = started_at
    row.last_status = "running"
    db.commit()


def record_module_run(
    db: Session,
    module_id: str,
    *,
    started_at: datetime,
    result: ModuleRunResult,
) -> None:
    ensure_seeded(db)
    row = db.query(DiscoveryModule).filter(DiscoveryModule.id == module_id).first()
    if row is None:
        return
    row.last_started_at = started_at
    row.last_finished_at = datetime.utcnow()
    if result.error:
        row.last_status = "error"
        row.last_error = (result.error or "")[:2000]
        row.error_count = int(row.error_count or 0) + 1
        row.items_failed = int(result.failed or 0)
    else:
        row.last_status = "skipped" if result.skipped_reason else "ok"
        row.last_error = None
        row.items_fetched = int(result.fetched or 0)
        row.items_inserted = int(result.inserted or 0)
        row.items_duplicate = int(result.duplicate or 0)
        row.items_failed = int(result.failed or 0)
    db.commit()
