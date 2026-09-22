"""Pipeline activity status for calm UI progress (DB read only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.pipeline_status_service import pipeline_status

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class PipelineStatusOut(BaseModel):
    collecting: bool
    unprocessed_raw: int
    published_issues: int
    draft_issues: int = 0
    last_topic_fetch_at: str | None = None
    last_accounts_fetch_at: str | None = None
    last_rss_fetch_at: str | None = None
    message: str


@router.get("/status", response_model=PipelineStatusOut)
def get_pipeline_status(db: Session = Depends(get_db)) -> PipelineStatusOut:
    return PipelineStatusOut(**pipeline_status(db))
