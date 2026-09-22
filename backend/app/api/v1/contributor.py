"""Contributor self-service API (soft user_id, no JWT)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas import (
    ContributorApplicationIn,
    ContributorApplicationOut,
    ContributorMeOut,
)
from app.services.contributor_service import ContributorError, ContributorService

router = APIRouter(prefix="/contributor", tags=["contributor"])


def _uid(user_id: str | None) -> str:
    return user_id or get_settings().default_user_id


def _raise(exc: ContributorError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/me", response_model=ContributorMeOut)
def contributor_me(
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ContributorMeOut:
    try:
        return ContributorService(db).get_me(_uid(user_id))
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/applications", response_model=ContributorApplicationOut)
def apply_contributor(
    body: ContributorApplicationIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ContributorApplicationOut:
    uid = _uid(body.user_id or user_id)
    try:
        return ContributorService(db).apply(
            uid,
            motivation=body.motivation,
            interests=body.interests,
            sample_text=body.sample_text,
        )
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.get("/applications/me", response_model=ContributorMeOut)
def my_application(
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ContributorMeOut:
    try:
        return ContributorService(db).get_me(_uid(user_id))
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover
