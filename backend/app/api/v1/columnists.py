"""Public TAKELEY columnist profile (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import ColumnistIssueListOut, ColumnistProfileOut
from app.services.columnist_service import ColumnistError, ColumnistService

router = APIRouter(prefix="/columnists", tags=["columnists"])


@router.get("/{columnist_id}", response_model=ColumnistProfileOut)
def get_columnist_profile(
    columnist_id: str,
    db: Session = Depends(get_db),
) -> ColumnistProfileOut:
    try:
        return ColumnistService(db).public_profile(columnist_id)
    except ColumnistError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{columnist_id}/issues", response_model=ColumnistIssueListOut)
def get_columnist_issues(
    columnist_id: str,
    limit: int = Query(10, ge=1, le=40),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ColumnistIssueListOut:
    try:
        return ColumnistService(db).public_issues(
            columnist_id, limit=limit, offset=offset
        )
    except ColumnistError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
