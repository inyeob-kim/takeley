"""Admin discovery module ON/OFF, pipeline switches, and RSS feeds."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.db.models import DiscoveryModule, PipelineControl, RssFeed
from app.db.session import get_db
from app.services import discovery_service

router = APIRouter(
    prefix="/admin/discovery",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class DiscoveryModuleOut(BaseModel):
    id: str
    enabled: bool
    interval_seconds: int | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    items_fetched: int = 0
    items_inserted: int = 0
    items_duplicate: int = 0
    items_failed: int = 0
    error_count: int = 0
    implemented: bool = False

    model_config = {"from_attributes": True}


class DiscoveryModuleIn(BaseModel):
    id: str
    enabled: bool | None = None
    interval_seconds: int | None = None


class PipelineOut(BaseModel):
    process_enabled: bool
    trend_enabled: bool
    push_enabled: bool
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PipelineIn(BaseModel):
    process_enabled: bool | None = None
    trend_enabled: bool | None = None
    push_enabled: bool | None = None


class RssFeedOut(BaseModel):
    id: str
    name: str
    url: str
    language: str = ""
    category: str = ""
    enabled: bool = True
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    error_count: int = 0

    model_config = {"from_attributes": True}


class RssFeedIn(BaseModel):
    name: str | None = None
    url: str | None = None
    language: str | None = None
    category: str | None = None
    enabled: bool | None = None


class DiscoveryStatsOut(BaseModel):
    modules: list[DiscoveryModuleOut]
    pipeline: PipelineOut
    rss_feeds: list[RssFeedOut]
    implemented: list[str]


def _module_out(row: DiscoveryModule) -> DiscoveryModuleOut:
    return DiscoveryModuleOut(
        id=row.id,
        enabled=row.enabled,
        interval_seconds=row.interval_seconds,
        last_started_at=row.last_started_at,
        last_finished_at=row.last_finished_at,
        last_status=row.last_status,
        last_error=row.last_error,
        items_fetched=row.items_fetched,
        items_inserted=row.items_inserted,
        items_duplicate=row.items_duplicate,
        items_failed=row.items_failed,
        error_count=row.error_count,
        implemented=row.id in discovery_service.IMPLEMENTED_MODULE_IDS,
    )


def _pipeline_out(row: PipelineControl) -> PipelineOut:
    return PipelineOut(
        process_enabled=row.process_enabled,
        trend_enabled=row.trend_enabled,
        push_enabled=row.push_enabled,
        updated_at=row.updated_at,
    )


def _feed_out(row: RssFeed) -> RssFeedOut:
    return RssFeedOut.model_validate(row)


@router.get("/modules", response_model=list[DiscoveryModuleOut])
def admin_list_modules(db: Session = Depends(get_db)) -> list[DiscoveryModuleOut]:
    return [_module_out(row) for row in discovery_service.list_modules(db)]


@router.put("/modules", response_model=list[DiscoveryModuleOut])
def admin_put_modules(
    payload: list[DiscoveryModuleIn],
    db: Session = Depends(get_db),
) -> list[DiscoveryModuleOut]:
    rows = discovery_service.update_modules(
        db, [item.model_dump(exclude_unset=True) for item in payload]
    )
    return [_module_out(row) for row in rows]


@router.get("/pipeline", response_model=PipelineOut)
def admin_get_pipeline(db: Session = Depends(get_db)) -> PipelineOut:
    return _pipeline_out(discovery_service.get_pipeline(db))


@router.put("/pipeline", response_model=PipelineOut)
def admin_put_pipeline(
    payload: PipelineIn,
    db: Session = Depends(get_db),
) -> PipelineOut:
    return _pipeline_out(
        discovery_service.update_pipeline(db, payload.model_dump(exclude_unset=True))
    )


@router.get("/rss-feeds", response_model=list[RssFeedOut])
def admin_list_feeds(db: Session = Depends(get_db)) -> list[RssFeedOut]:
    return [_feed_out(row) for row in discovery_service.list_feeds(db)]


@router.post("/rss-feeds", response_model=RssFeedOut)
def admin_create_feed(
    payload: RssFeedIn,
    db: Session = Depends(get_db),
) -> RssFeedOut:
    return _feed_out(
        discovery_service.create_feed(db, payload.model_dump(exclude_unset=True))
    )


@router.patch("/rss-feeds/{feed_id}", response_model=RssFeedOut)
def admin_update_feed(
    feed_id: str,
    payload: RssFeedIn,
    db: Session = Depends(get_db),
) -> RssFeedOut:
    return _feed_out(
        discovery_service.update_feed(
            db, feed_id, payload.model_dump(exclude_unset=True)
        )
    )


@router.delete("/rss-feeds/{feed_id}")
def admin_delete_feed(feed_id: str, db: Session = Depends(get_db)) -> dict:
    discovery_service.delete_feed(db, feed_id)
    return {"ok": True}


@router.get("/stats", response_model=DiscoveryStatsOut)
def admin_discovery_stats(db: Session = Depends(get_db)) -> DiscoveryStatsOut:
    data = discovery_service.stats(db)
    return DiscoveryStatsOut(
        modules=[_module_out(row) for row in data["modules"]],
        pipeline=_pipeline_out(data["pipeline"]),
        rss_feeds=[_feed_out(row) for row in data["rss_feeds"]],
        implemented=data["implemented"],
    )
