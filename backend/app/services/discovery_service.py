"""Admin-facing discovery module / pipeline / RSS feed settings."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import DiscoveryModule, PipelineControl, RssFeed
from app.discovery.state import PIPELINE_ID, ensure_seeded

# Implemented modules that the worker can actually run.
IMPLEMENTED_MODULE_IDS = frozenset(
    {"x", "rss", "trends", "reddit", "hacker_news", "official"}
)


def _ensure():
    return ensure_seeded, PIPELINE_ID


def list_modules(db: Session) -> list[DiscoveryModule]:
    ensure_seeded, _ = _ensure()
    ensure_seeded(db)
    rows = db.query(DiscoveryModule).all()
    order = ["x", "rss", "trends", "reddit", "hacker_news", "official"]
    by_id = {row.id: row for row in rows}
    return [by_id[i] for i in order if i in by_id] + [
        row for row in rows if row.id not in order
    ]


def update_modules(db: Session, payload: list[dict]) -> list[DiscoveryModule]:
    ensure_seeded, _ = _ensure()
    ensure_seeded(db)
    by_id = {row.id: row for row in db.query(DiscoveryModule).all()}
    for item in payload:
        module_id = str(item.get("id") or "")
        row = by_id.get(module_id)
        if row is None:
            continue
        if "enabled" in item:
            row.enabled = bool(item["enabled"])
        if "interval_seconds" in item and item["interval_seconds"] is not None:
            row.interval_seconds = int(item["interval_seconds"])
    db.commit()
    return list_modules(db)


def get_pipeline(db: Session) -> PipelineControl:
    ensure_seeded, pipeline_id = _ensure()
    ensure_seeded(db)
    row = db.query(PipelineControl).filter(PipelineControl.id == pipeline_id).first()
    assert row is not None
    return row


def update_pipeline(db: Session, payload: dict) -> PipelineControl:
    row = get_pipeline(db)
    if "process_enabled" in payload:
        row.process_enabled = bool(payload["process_enabled"])
    if "trend_enabled" in payload:
        row.trend_enabled = bool(payload["trend_enabled"])
    if "push_enabled" in payload:
        row.push_enabled = bool(payload["push_enabled"])
    db.commit()
    db.refresh(row)
    return row


def _validate_feed_url(url: str) -> str:
    text = (url or "").strip()
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="RSS URL은 http:// 또는 https:// 여야 해요.")
    return text


def list_feeds(db: Session) -> list[RssFeed]:
    ensure_seeded(db)
    return db.query(RssFeed).order_by(RssFeed.name.asc()).all()


def create_feed(db: Session, payload: dict) -> RssFeed:
    url = _validate_feed_url(str(payload.get("url") or ""))
    name = (payload.get("name") or "").strip() or url
    row = RssFeed(
        name=name[:128],
        url=url,
        language=(payload.get("language") or "")[:16],
        category=(payload.get("category") or "")[:32],
        enabled=bool(payload.get("enabled", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_feed(db: Session, feed_id: str, payload: dict) -> RssFeed:
    row = db.query(RssFeed).filter(RssFeed.id == feed_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="피드를 찾지 못했어요.")
    if "url" in payload and payload["url"] is not None:
        row.url = _validate_feed_url(str(payload["url"]))
    if "name" in payload and payload["name"] is not None:
        row.name = str(payload["name"]).strip()[:128] or row.name
    if "language" in payload and payload["language"] is not None:
        row.language = str(payload["language"])[:16]
    if "category" in payload and payload["category"] is not None:
        row.category = str(payload["category"])[:32]
    if "enabled" in payload:
        row.enabled = bool(payload["enabled"])
    db.commit()
    db.refresh(row)
    return row


def delete_feed(db: Session, feed_id: str) -> None:
    row = db.query(RssFeed).filter(RssFeed.id == feed_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="피드를 찾지 못했어요.")
    db.delete(row)
    db.commit()


def stats(db: Session) -> dict:
    ensure_seeded, _ = _ensure()
    ensure_seeded(db)
    modules = list_modules(db)
    pipeline = get_pipeline(db)
    feeds = list_feeds(db)
    return {
        "modules": modules,
        "pipeline": pipeline,
        "rss_feeds": feeds,
        "implemented": sorted(IMPLEMENTED_MODULE_IDS),
    }
