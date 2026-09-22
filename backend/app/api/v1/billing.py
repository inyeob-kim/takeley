from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas import (
    DeviceRegisterIn,
    DeviceRegisterOut,
    EntitlementOut,
    ProductIdsOut,
)
from app.services.device_service import DeviceService
from app.services.entitlement_service import EntitlementService

router = APIRouter(tags=["billing"])


@router.post("/devices/register", response_model=DeviceRegisterOut)
def register_device(
    body: DeviceRegisterIn,
    db: Session = Depends(get_db),
) -> DeviceRegisterOut:
    """Anonymous device signup — no email. Returns user_id for subsequent calls."""
    try:
        return DeviceService(db).register(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/billing/entitlements", response_model=EntitlementOut)
def get_entitlements(
    user_id: str | None = Query(None),
    device_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> EntitlementOut:
    svc = EntitlementService(db)
    try:
        if user_id:
            return svc.entitlements_for_user(user_id)
        if device_id:
            return svc.entitlements_for_device(device_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail="user_id or device_id required")


@router.get("/billing/products", response_model=ProductIdsOut)
def get_product_ids() -> ProductIdsOut:
    settings = get_settings()
    return ProductIdsOut(
        ios_product_id=settings.iap_ios_product_id,
        android_product_id=settings.iap_android_product_id,
    )
