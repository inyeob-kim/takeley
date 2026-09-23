"""Device-first anonymous registration (no email/password)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Columnist,
    DeviceToken,
    IssueComment,
    IssueFollow,
    IssueTakeReaction,
    IssueUserEvent,
    IssueView,
    Participation,
    PushNotification,
    PushNotificationLog,
    UserPreference,
    WatchlistItem,
)
from app.db.repositories import UserRepository
from app.schemas import DeviceRegisterIn, DeviceRegisterOut
from app.services.entitlement_service import EntitlementService, user_to_out


class DeviceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def register(self, payload: DeviceRegisterIn) -> DeviceRegisterOut:
        user, created = self.users.get_or_create_device(
            device_id=payload.device_id,
            platform=payload.platform,
            app_version=payload.app_version,
        )
        # Keep plan in sync with any existing IAP rows (e.g. restore).
        EntitlementService(self.db).reconcile_user_plan(user.id)
        user = self.users.get_by_id(user.id)
        assert user is not None
        return DeviceRegisterOut(user=user_to_out(user), created=created)

    def delete_device(self, *, user_id: str, device_id: str) -> None:
        """Erase this device session and user-generated rows (App Store 5.1.1(v))."""
        user = self.users.get_by_id(user_id.strip())
        if user is None or user.device_id != device_id.strip():
            raise ValueError("device_mismatch")
        uid = user.id
        for model in (
            IssueTakeReaction,
            IssueComment,
            Participation,
            IssueFollow,
            IssueView,
            IssueUserEvent,
            WatchlistItem,
            UserPreference,
            DeviceToken,
            PushNotification,
            PushNotificationLog,
        ):
            self.db.query(model).filter(model.user_id == uid).delete(
                synchronize_session=False
            )
        self.db.query(Columnist).filter(Columnist.user_id == uid).update(
            {Columnist.user_id: None}, synchronize_session=False
        )
        self.db.delete(user)
        self.db.commit()
