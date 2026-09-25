"""Issue-nested IssueTake routes (깊이 있는 생각)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas import (
    IssueTakeIn,
    IssueTakeListOut,
    IssueTakeOut,
    IssueTakePublicOut,
    IssueTakeReactionOut,
    IssueTakeUpdateIn,
)
from app.services.contributor_service import ContributorError
from app.services.take_service import TakeService

router = APIRouter(prefix="/issues", tags=["issue-takes"])


def _uid(user_id: str | None) -> str:
    return user_id or get_settings().default_user_id


def _raise(exc: ContributorError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{issue_id}/takes", response_model=IssueTakeListOut)
def list_published_takes(
    issue_id: str,
    limit: int = Query(20, ge=1, le=50),
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueTakeListOut:
    try:
        return TakeService(db).list_published(
            issue_id, user_id=user_id, limit=limit
        )
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/{issue_id}/takes", response_model=IssueTakeOut)
def create_take(
    issue_id: str,
    body: IssueTakeIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueTakeOut:
    uid = _uid(body.user_id or user_id)
    try:
        return TakeService(db).create(
            issue_id,
            user_id=uid,
            title=body.title,
            body=body.body,
            source_urls=body.source_urls,
            body_issue_id=body.issue_id,
        )
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.get(
    "/{issue_id}/takes/mine",
    response_model=list[IssueTakeOut],
)
def list_my_takes(
    issue_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[IssueTakeOut]:
    try:
        return TakeService(db).list_mine(issue_id, user_id=_uid(user_id))
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.get(
    "/{issue_id}/takes/{take_id}",
    response_model=IssueTakePublicOut | IssueTakeOut,
)
def get_take(
    issue_id: str,
    take_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueTakePublicOut | IssueTakeOut:
    try:
        return TakeService(db).get_for_reader(
            issue_id, take_id, user_id=_uid(user_id), record_view=True
        )
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.patch("/{issue_id}/takes/{take_id}", response_model=IssueTakeOut)
def update_take(
    issue_id: str,
    take_id: str,
    body: IssueTakeUpdateIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueTakeOut:
    uid = _uid(body.user_id or user_id)
    try:
        return TakeService(db).update(
            issue_id,
            take_id,
            user_id=uid,
            title=body.title,
            body=body.body,
            source_urls=body.source_urls,
        )
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/{issue_id}/takes/{take_id}/submit", response_model=IssueTakeOut)
def submit_take(
    issue_id: str,
    take_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueTakeOut:
    try:
        return TakeService(db).submit(issue_id, take_id, user_id=_uid(user_id))
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/{issue_id}/takes/{take_id}/withdraw", response_model=IssueTakeOut)
def withdraw_take(
    issue_id: str,
    take_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueTakeOut:
    try:
        return TakeService(db).withdraw(issue_id, take_id, user_id=_uid(user_id))
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post(
    "/{issue_id}/takes/{take_id}/reaction",
    response_model=IssueTakeReactionOut,
)
def react_take(
    issue_id: str,
    take_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueTakeReactionOut:
    try:
        return TakeService(db).add_reaction(
            issue_id, take_id, user_id=_uid(user_id)
        )
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover
