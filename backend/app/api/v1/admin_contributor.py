"""Admin Contributor + IssueTake moderation (X-Admin-Key)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.db.session import get_db
from app.schemas import (
    AdminContributorRejectIn,
    AdminTakeListOut,
    AdminTakeRejectIn,
    ContributorApplicationListOut,
    ContributorApplicationOut,
    IssueTakeOut,
)
from app.services.contributor_service import ContributorError, ContributorService
from app.services.take_service import TakeService

router = APIRouter(
    prefix="/admin/contributor",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


def _raise(exc: ContributorError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/applications", response_model=ContributorApplicationListOut)
def admin_list_applications(
    status: str = Query("PENDING", pattern="^(PENDING|APPROVED|REJECTED)$"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ContributorApplicationListOut:
    items = ContributorService(db).list_applications(status=status, limit=limit)
    return ContributorApplicationListOut(items=items, count=len(items))


@router.post(
    "/applications/{application_id}/approve",
    response_model=ContributorApplicationOut,
)
def admin_approve_application(
    application_id: str,
    db: Session = Depends(get_db),
) -> ContributorApplicationOut:
    try:
        return ContributorService(db).approve_application(application_id)
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post(
    "/applications/{application_id}/reject",
    response_model=ContributorApplicationOut,
)
def admin_reject_application(
    application_id: str,
    body: AdminContributorRejectIn | None = None,
    db: Session = Depends(get_db),
) -> ContributorApplicationOut:
    reason = body.reason if body else None
    try:
        return ContributorService(db).reject_application(
            application_id, reason=reason
        )
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post(
    "/applications/{application_id}/suspend",
    response_model=ContributorApplicationOut,
)
def admin_suspend_contributor(
    application_id: str,
    body: AdminContributorRejectIn | None = None,
    db: Session = Depends(get_db),
) -> ContributorApplicationOut:
    """Revoke Contributor writing rights (SUSPENDED). Published takes remain."""
    reason = body.reason if body else None
    try:
        return ContributorService(db).suspend_contributor(
            application_id, reason=reason
        )
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post(
    "/applications/{application_id}/reinstate",
    response_model=ContributorApplicationOut,
)
def admin_reinstate_contributor(
    application_id: str,
    db: Session = Depends(get_db),
) -> ContributorApplicationOut:
    """Restore Contributor writing rights after suspend."""
    try:
        return ContributorService(db).reinstate_contributor(application_id)
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.get("/takes", response_model=AdminTakeListOut)
def admin_list_takes(
    status: str = Query(
        "pending_review",
        pattern="^(draft|pending_review|published|rejected)$",
    ),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdminTakeListOut:
    items = TakeService(db).admin_list(status=status, limit=limit)
    return AdminTakeListOut(items=items, count=len(items))


@router.post("/takes/{take_id}/publish", response_model=IssueTakeOut)
def admin_publish_take(
    take_id: str,
    db: Session = Depends(get_db),
) -> IssueTakeOut:
    try:
        return TakeService(db).admin_publish(take_id)
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/takes/{take_id}/reject", response_model=IssueTakeOut)
def admin_reject_take(
    take_id: str,
    body: AdminTakeRejectIn | None = None,
    db: Session = Depends(get_db),
) -> IssueTakeOut:
    reason = body.reason if body else None
    try:
        return TakeService(db).admin_reject(take_id, reason=reason)
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/takes/{take_id}/unpublish", response_model=IssueTakeOut)
def admin_unpublish_take(
    take_id: str,
    body: AdminTakeRejectIn | None = None,
    db: Session = Depends(get_db),
) -> IssueTakeOut:
    reason = body.reason if body else None
    try:
        return TakeService(db).admin_unpublish(take_id, reason=reason)
    except ContributorError as exc:
        _raise(exc)
        raise  # pragma: no cover
