"""Admin UGC report queue — act within 24 hours."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.db.session import get_db
from app.schemas import AdminReportResolveIn, ContentReportListOut, ContentReportOut
from app.services.safety_service import SafetyError, SafetyService

router = APIRouter(
    prefix="/admin/reports",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=ContentReportListOut)
def admin_list_reports(
    status: str = Query("open", pattern="^(open|removed|dismissed)$"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ContentReportListOut:
    items = SafetyService(db).list_reports(status=status, limit=limit)
    return ContentReportListOut(items=items, count=len(items))


@router.post("/{report_id}/resolve", response_model=ContentReportOut)
def admin_resolve_report(
    report_id: str,
    body: AdminReportResolveIn,
    db: Session = Depends(get_db),
) -> ContentReportOut:
    try:
        return SafetyService(db).resolve(
            report_id, action=body.action, eject=body.eject
        )
    except SafetyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
