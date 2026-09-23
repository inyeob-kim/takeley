"""Admin TAKELEY columnist roster (X-Admin-Key)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.db.session import get_db
from app.schemas import (
    AdminColumnistIn,
    AdminColumnistPatchIn,
    ColumnistListOut,
    ColumnistOut,
)
from app.services.columnist_service import ColumnistError, ColumnistService

router = APIRouter(
    prefix="/admin/columnists",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


def _raise(exc: ColumnistError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("", response_model=ColumnistListOut)
def admin_list_columnists(
    status: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ColumnistListOut:
    try:
        return ColumnistService(db).list_admin(status=status, limit=limit)
    except ColumnistError as exc:
        _raise(exc)


@router.post("", response_model=ColumnistOut)
def admin_create_columnist(
    body: AdminColumnistIn,
    db: Session = Depends(get_db),
) -> ColumnistOut:
    try:
        return ColumnistService(db).create(
            display_name=body.display_name,
            headline=body.headline,
            bio=body.bio,
            specialties=body.specialties,
            contact_email=body.contact_email,
            show_email=body.show_email,
            image_url=body.image_url,
            status=body.status,
            sort_order=body.sort_order,
        )
    except ColumnistError as exc:
        _raise(exc)


@router.get("/{columnist_id}", response_model=ColumnistOut)
def admin_get_columnist(
    columnist_id: str,
    db: Session = Depends(get_db),
) -> ColumnistOut:
    try:
        return ColumnistService(db).get_admin(columnist_id)
    except ColumnistError as exc:
        _raise(exc)


@router.patch("/{columnist_id}", response_model=ColumnistOut)
def admin_patch_columnist(
    columnist_id: str,
    body: AdminColumnistPatchIn,
    db: Session = Depends(get_db),
) -> ColumnistOut:
    try:
        return ColumnistService(db).update(
            columnist_id,
            display_name=body.display_name,
            headline=body.headline,
            bio=body.bio,
            specialties=body.specialties,
            contact_email=body.contact_email,
            show_email=body.show_email,
            image_url=body.image_url,
            clear_image=body.clear_image,
            status=body.status,
            sort_order=body.sort_order,
        )
    except ColumnistError as exc:
        _raise(exc)


@router.post("/{columnist_id}/image", response_model=ColumnistOut)
async def admin_upload_columnist_image(
    columnist_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ColumnistOut:
    try:
        return await ColumnistService(db).upload_image(columnist_id, file)
    except ColumnistError as exc:
        _raise(exc)
