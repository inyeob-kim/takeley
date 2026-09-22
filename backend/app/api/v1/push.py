from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    PushDeviceRegisterIn,
    PushDeviceRegisterOut,
    PushTemplateListOut,
    PushTemplateOut,
    PushTemplateUpdateIn,
)
from app.services.push_template_service import list_templates, update_template
from app.services.push_token_service import PushTokenService

router = APIRouter(prefix="/push", tags=["push"])


@router.post("/devices/register", response_model=PushDeviceRegisterOut)
def register_push_device(
    body: PushDeviceRegisterIn,
    db: Session = Depends(get_db),
) -> PushDeviceRegisterOut:
    """Register an FCM token for a user (device_id or user_id). No FCM send here."""
    try:
        return PushTokenService(db).register(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/templates", response_model=PushTemplateListOut)
def get_push_templates(db: Session = Depends(get_db)) -> PushTemplateListOut:
    rows = list_templates(db)
    items = [PushTemplateOut.model_validate(r) for r in rows]
    return PushTemplateListOut(items=items, count=len(items))


@router.patch("/templates/{category}", response_model=PushTemplateOut)
def patch_push_template(
    category: str,
    body: PushTemplateUpdateIn,
    db: Session = Depends(get_db),
) -> PushTemplateOut:
    try:
        row = update_template(
            db,
            category,
            title_template=body.title_template,
            body_template=body.body_template,
            is_active=body.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PushTemplateOut.model_validate(row)
