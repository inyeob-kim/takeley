"""Admin X ingest schedule, budgets, and cost readout."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.db.session import get_db
from app.services import industry_search_config, x_ingest_admin

router = APIRouter(
    prefix="/admin/x-ingest",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class XIngestConfigOut(BaseModel):
    scan_mode: str
    scan_hours_kst: str
    scan_window_minutes: int
    morning_lane: str
    afternoon_lane: str
    night_lane: str
    lanes_per_scan: int
    max_results: int
    industries: str
    accounts_on: str
    track_accounts: str
    dynamic_mode: str
    hot_enabled: bool
    hot_interval_minutes: int
    hot_idle_scans: int
    hot_max_hours: int
    hot_reply_spike: int
    understand_budget: int
    industry_slot_reserve: bool
    usd_per_post: float
    usd_per_user: float
    opposite_lane_count: int = 2
    daily_post_budget: int = 400
    updated_at: datetime | None = None


class XIngestConfigIn(BaseModel):
    scan_mode: str | None = None
    scan_hours_kst: str | None = None
    scan_window_minutes: int | None = None
    morning_lane: str | None = None
    afternoon_lane: str | None = None
    night_lane: str | None = None
    lanes_per_scan: int | None = None
    max_results: int | None = None
    industries: str | None = None
    accounts_on: str | None = None
    track_accounts: str | None = None
    dynamic_mode: str | None = None
    hot_enabled: bool | None = None
    hot_interval_minutes: int | None = None
    hot_idle_scans: int | None = None
    hot_max_hours: int | None = None
    hot_reply_spike: int | None = None
    understand_budget: int | None = None
    industry_slot_reserve: bool | None = None
    usd_per_post: float | None = None
    usd_per_user: float | None = None
    opposite_lane_count: int | None = None
    daily_post_budget: int | None = None


class IndustryStatOut(BaseModel):
    industry: str
    label: str
    posts: int
    korea_posts: int = 0
    global_posts: int = 0
    processed: int
    issues: int
    updates: int = 0
    api_calls: int
    estimated_usd: float
    usd_per_issue: float | None = None


class SlotStatOut(BaseModel):
    slot: str
    posts: int
    issues: int = 0
    estimated_usd: float = 0
    usd_per_issue: float | None = None


class HotTopicOut(BaseModel):
    industry: str
    lane: str
    idle: int
    until: str | None = None


class XIngestStatsOut(BaseModel):
    days: int
    posts_fetched: int
    search_calls: int
    timeline_calls: int
    user_lookups: int
    new_issues: int
    updates: int = 0
    estimated_usd: float
    usd_per_new_issue: float | None = None
    korea_posts: int = 0
    global_posts: int = 0
    dynamic_queries: int = 0
    hot_scans: int = 0
    slots: list[SlotStatOut] = Field(default_factory=list)
    industries: list[IndustryStatOut] = Field(default_factory=list)
    hot: list[HotTopicOut] = Field(default_factory=list)
    last_slot_key: str | None = None


def _out(row) -> XIngestConfigOut:
    return XIngestConfigOut(
        scan_mode=row.scan_mode,
        scan_hours_kst=row.scan_hours_kst,
        scan_window_minutes=row.scan_window_minutes,
        morning_lane=row.morning_lane,
        afternoon_lane=row.afternoon_lane,
        night_lane=row.night_lane,
        lanes_per_scan=row.lanes_per_scan,
        max_results=row.max_results,
        industries=row.industries,
        accounts_on=row.accounts_on,
        track_accounts=row.track_accounts,
        dynamic_mode=row.dynamic_mode,
        hot_enabled=row.hot_enabled,
        hot_interval_minutes=row.hot_interval_minutes,
        hot_idle_scans=row.hot_idle_scans,
        hot_max_hours=row.hot_max_hours,
        hot_reply_spike=row.hot_reply_spike,
        understand_budget=row.understand_budget,
        industry_slot_reserve=row.industry_slot_reserve,
        usd_per_post=row.usd_per_post,
        usd_per_user=row.usd_per_user,
        opposite_lane_count=int(getattr(row, "opposite_lane_count", 2) or 0),
        daily_post_budget=int(getattr(row, "daily_post_budget", 400) or 0),
        updated_at=row.updated_at,
    )


class IndustrySearchOut(BaseModel):
    industry_key: str
    label: str
    enabled: bool
    keywords_ko: str
    keywords_en: str
    exclude_ko: str
    exclude_en: str
    priority: str
    frequency: str
    max_results: int | None = None


class IndustrySearchIn(BaseModel):
    industry_key: str
    enabled: bool | None = None
    keywords_ko: str | None = None
    keywords_en: str | None = None
    exclude_ko: str | None = None
    exclude_en: str | None = None
    priority: str | None = None
    frequency: str | None = None
    max_results: int | None = None


@router.get("/config", response_model=XIngestConfigOut)
def admin_get_x_ingest_config(db: Session = Depends(get_db)) -> XIngestConfigOut:
    return _out(x_ingest_admin.get_or_create(db))


@router.put("/config", response_model=XIngestConfigOut)
def admin_put_x_ingest_config(
    body: XIngestConfigIn,
    db: Session = Depends(get_db),
) -> XIngestConfigOut:
    try:
        row = x_ingest_admin.update_config(
            db, body.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _out(row)


@router.get("/industries", response_model=list[IndustrySearchOut])
def admin_list_industries(db: Session = Depends(get_db)) -> list[IndustrySearchOut]:
    rows = industry_search_config.ensure_seeded(db)
    by_key = {row.industry_key: row for row in rows}
    ordered = [
        by_key[key]
        for key in industry_search_config.ISSUE_INDUSTRY_KEYS
        if key in by_key
    ]
    return [IndustrySearchOut.model_validate(industry_search_config.to_public(row)) for row in ordered]


@router.put("/industries", response_model=list[IndustrySearchOut])
def admin_put_industries(
    body: list[IndustrySearchIn],
    db: Session = Depends(get_db),
) -> list[IndustrySearchOut]:
    try:
        rows = industry_search_config.update_industries(
            db, [item.model_dump(exclude_unset=True) for item in body]
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    by_key = {row.industry_key: row for row in rows}
    ordered = [
        by_key[key]
        for key in industry_search_config.ISSUE_INDUSTRY_KEYS
        if key in by_key
    ]
    return [IndustrySearchOut.model_validate(industry_search_config.to_public(row)) for row in ordered]


@router.get("/stats", response_model=XIngestStatsOut)
def admin_x_ingest_stats(
    days: int = 7,
    db: Session = Depends(get_db),
) -> XIngestStatsOut:
    return XIngestStatsOut.model_validate(
        x_ingest_admin.stats(db, days=max(1, min(days, 90)))
    )
