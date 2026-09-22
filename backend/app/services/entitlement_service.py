"""Pro entitlement reconcile (ssamdaeshin-compatible, device users)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import User
from app.db.repositories import SubscriptionPaymentRepository, UserRepository
from app.schemas import EntitlementOut, UserOut

logger = logging.getLogger(__name__)


def _is_pro(plan_type: str, plan_expire_at: datetime | None, *, now: datetime) -> bool:
    if plan_type != "PRO":
        return False
    if plan_expire_at is None:
        return True
    exp = plan_expire_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    now_aware = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return exp > now_aware


def user_to_out(user: User, *, now: datetime | None = None) -> UserOut:
    now = now or datetime.now(timezone.utc)
    return UserOut(
        id=user.id,
        device_id=user.device_id,
        platform=user.platform,
        plan_type=user.plan_type or "FREE",
        plan_expire_at=user.plan_expire_at,
        is_pro=_is_pro(user.plan_type or "FREE", user.plan_expire_at, now=now),
        status=user.status or "active",
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
    )


class EntitlementService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.payments = SubscriptionPaymentRepository(db)

    def reconcile_user_plan(self, user_id: str) -> tuple[str, datetime | None]:
        """
        From PAID subscription_payments:
        - max(expires_at) > now → PRO
        - else → FREE
        """
        user = self.users.get_by_id(user_id)
        if not user:
            raise ValueError(f"user not found: {user_id}")

        now = datetime.utcnow()
        max_exp = self.payments.max_paid_expires_at(user_id)
        if max_exp and max_exp > now:
            user.plan_type = "PRO"
            user.plan_expire_at = max_exp
        else:
            user.plan_type = "FREE"
            user.plan_expire_at = None
        self.db.commit()
        self.db.refresh(user)
        logger.info(
            "entitlement_reconcile user=%s plan=%s expire=%s",
            user_id,
            user.plan_type,
            user.plan_expire_at,
        )
        return user.plan_type, user.plan_expire_at

    def entitlements_for_user(self, user_id: str) -> EntitlementOut:
        user = self.users.get_by_id(user_id)
        if not user:
            raise ValueError(f"user not found: {user_id}")
        # Soft refresh from payments so expired PRO drops without verify call.
        self.reconcile_user_plan(user_id)
        user = self.users.get_by_id(user_id)
        assert user is not None
        now = datetime.now(timezone.utc)
        out = user_to_out(user, now=now)
        return EntitlementOut(
            user_id=out.id,
            pro=out.is_pro,
            plan_type=out.plan_type,  # type: ignore[arg-type]
            plan_expire_at=out.plan_expire_at,
        )

    def entitlements_for_device(self, device_id: str) -> EntitlementOut:
        user = self.users.get_by_device_id(device_id)
        if not user:
            raise ValueError(f"device not registered: {device_id}")
        return self.entitlements_for_user(user.id)
