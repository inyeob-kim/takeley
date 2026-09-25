"""User-facing UGC safety: report, hide, block, delete own comment."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas import (
    ContentHideIn,
    ContentReportIn,
    SafetyOkOut,
    UserBlockIn,
)
from app.services.contributor_service import ContributorError
from app.services.safety_service import SafetyError, SafetyService

router = APIRouter(prefix="/safety", tags=["safety"])


def _uid(user_id: str | None) -> str:
    return user_id or get_settings().default_user_id


def _raise(exc: SafetyError | ContributorError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/report", response_model=SafetyOkOut)
def report_content(
    body: ContentReportIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> SafetyOkOut:
    try:
        return SafetyService(db).report(
            user_id=_uid(body.user_id or user_id),
            target_type=body.target_type,
            target_id=body.target_id,
            reason=body.reason,
            details=body.details,
        )
    except (SafetyError, ContributorError) as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/hide", response_model=SafetyOkOut)
def hide_content(
    body: ContentHideIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> SafetyOkOut:
    try:
        return SafetyService(db).hide(
            user_id=_uid(body.user_id or user_id),
            target_type=body.target_type,
            target_id=body.target_id,
        )
    except (SafetyError, ContributorError) as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/block", response_model=SafetyOkOut)
def block_user(
    body: UserBlockIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> SafetyOkOut:
    try:
        return SafetyService(db).block_user(
            user_id=_uid(body.user_id or user_id),
            blocked_user_id=body.blocked_user_id,
        )
    except (SafetyError, ContributorError) as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.delete("/comments/{comment_id}", response_model=SafetyOkOut)
def delete_own_comment(
    comment_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> SafetyOkOut:
    try:
        return SafetyService(db).delete_own_comment(
            user_id=_uid(user_id), comment_id=comment_id
        )
    except (SafetyError, ContributorError) as exc:
        _raise(exc)
        raise  # pragma: no cover
