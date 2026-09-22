"""Admin Issue review API — separate portal only (X-Admin-Key)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.db.session import get_db
from app.schemas import IssueListOut, IssueOut
from app.services.admin_issue_service import AdminIssueService

router = APIRouter(
    prefix="/admin/issues",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class AdminRejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminIssueUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    summary: str | None = None
    why_it_matters: str | None = None
    column_body: str | None = None
    column_author_name: str | None = Field(default=None, max_length=128)
    column_author_image_url: str | None = None
    clear_column_author_image: bool = False
    image_url: str | None = None
    clear_image: bool = False
    key_points: list[str] | None = None
    category: str | None = Field(default=None, max_length=64)
    participation_suitable: bool | None = None
    participation_question: str | None = None
    participation_options: list[str] | None = None
    show_sources: bool | None = None
    push_title: str | None = Field(default=None, max_length=80)
    push_body: str | None = Field(default=None, max_length=160)


class AdminCountsOut(BaseModel):
    draft: int
    published: int
    rejected: int


class AdminColumnMediaOut(BaseModel):
    """Inline column image upload — does not change cover image_url."""

    url: str


@router.get("/counts", response_model=AdminCountsOut)
def admin_issue_counts(db: Session = Depends(get_db)) -> AdminCountsOut:
    return AdminCountsOut(**AdminIssueService(db).counts())


@router.get("", response_model=IssueListOut)
def admin_list_issues(
    status: str = Query("draft", pattern="^(draft|published|rejected)$"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> IssueListOut:
    return AdminIssueService(db).list_by_status(status=status, limit=limit)


@router.get("/{issue_id}", response_model=IssueOut)
def admin_get_issue(issue_id: str, db: Session = Depends(get_db)) -> IssueOut:
    out = AdminIssueService(db).get(issue_id)
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.patch("/{issue_id}", response_model=IssueOut)
def admin_update_issue(
    issue_id: str,
    body: AdminIssueUpdateIn,
    db: Session = Depends(get_db),
) -> IssueOut:
    try:
        out = AdminIssueService(db).update(
            issue_id,
            title=body.title,
            summary=body.summary,
            why_it_matters=body.why_it_matters,
            column_body=body.column_body,
            column_author_name=body.column_author_name,
            column_author_image_url=body.column_author_image_url,
            clear_column_author_image=body.clear_column_author_image,
            image_url=body.image_url,
            clear_image=body.clear_image,
            key_points=body.key_points,
            category=body.category,
            participation_suitable=body.participation_suitable,
            participation_question=body.participation_question,
            participation_options=body.participation_options,
            show_sources=body.show_sources,
            push_title=body.push_title,
            push_body=body.push_body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.post("/{issue_id}/image", response_model=IssueOut)
async def admin_upload_issue_image(
    issue_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> IssueOut:
    try:
        out = await AdminIssueService(db).upload_image(issue_id, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.post("/{issue_id}/column-media", response_model=AdminColumnMediaOut)
async def admin_upload_column_media(
    issue_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AdminColumnMediaOut:
    """Save an image for column markdown; cover image is unchanged."""
    try:
        url = await AdminIssueService(db).upload_column_media(issue_id, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not url:
        raise HTTPException(status_code=404, detail="Issue not found")
    return AdminColumnMediaOut(url=url)


@router.post("/{issue_id}/publish", response_model=IssueOut)
def admin_publish_issue(issue_id: str, db: Session = Depends(get_db)) -> IssueOut:
    try:
        out = AdminIssueService(db).publish(issue_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.post("/{issue_id}/unpublish", response_model=IssueOut)
def admin_unpublish_issue(
    issue_id: str, db: Session = Depends(get_db)
) -> IssueOut:
    try:
        out = AdminIssueService(db).unpublish(issue_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.post("/{issue_id}/reject", response_model=IssueOut)
def admin_reject_issue(
    issue_id: str,
    body: AdminRejectIn | None = None,
    db: Session = Depends(get_db),
) -> IssueOut:
    try:
        out = AdminIssueService(db).reject(
            issue_id, reason=(body.reason if body else None)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out
