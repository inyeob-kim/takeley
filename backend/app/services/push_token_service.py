"""FCM token registration (API-facing). Does not send push."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import DeviceToken, User
from app.db.repositories import UserRepository
from app.schemas import PushDeviceRegisterIn, PushDeviceRegisterOut


class PushTokenService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def _resolve_user_id(self, payload: PushDeviceRegisterIn) -> str:
        if payload.user_id:
            user = self.users.get_by_id(payload.user_id)
            if not user:
                raise ValueError("user_id not found")
            return user.id
        if payload.device_id:
            user = (
                self.db.query(User)
                .filter(User.device_id == payload.device_id)
                .one_or_none()
            )
            if not user:
                raise ValueError("device_id not registered; call /devices/register first")
            return user.id
        raise ValueError("user_id or device_id required")

    def register(self, payload: PushDeviceRegisterIn) -> PushDeviceRegisterOut:
        user_id = self._resolve_user_id(payload)
        token = payload.fcm_token.strip()
        if not token:
            raise ValueError("fcm_token required")

        client_device_id = payload.client_device_id or payload.device_id
        now = datetime.utcnow()

        existing = (
            self.db.query(DeviceToken)
            .filter(DeviceToken.fcm_token == token)
            .one_or_none()
        )
        created = existing is None
        if existing:
            existing.user_id = user_id
            existing.platform = payload.platform
            existing.client_device_id = client_device_id
            existing.app_version = payload.app_version
            existing.is_active = True
            existing.last_seen_at = now
            existing.updated_at = now
            row = existing
        else:
            if client_device_id:
                # Same physical device → replace prior token for that client id.
                stale = (
                    self.db.query(DeviceToken)
                    .filter(
                        DeviceToken.user_id == user_id,
                        DeviceToken.client_device_id == client_device_id,
                        DeviceToken.is_active.is_(True),
                    )
                    .all()
                )
                for old in stale:
                    old.is_active = False
                    old.updated_at = now
            row = DeviceToken(
                user_id=user_id,
                fcm_token=token,
                platform=payload.platform,
                client_device_id=client_device_id,
                app_version=payload.app_version,
                is_active=True,
                last_seen_at=now,
            )
            self.db.add(row)

        self.db.commit()
        self.db.refresh(row)
        return PushDeviceRegisterOut(
            id=row.id,
            user_id=row.user_id,
            platform=row.platform,
            is_active=row.is_active,
            created=created,
        )

    def list_active(self, user_id: str) -> list[DeviceToken]:
        return (
            self.db.query(DeviceToken)
            .filter(DeviceToken.user_id == user_id, DeviceToken.is_active.is_(True))
            .all()
        )

    def deactivate_token(self, fcm_token: str) -> None:
        row = (
            self.db.query(DeviceToken)
            .filter(DeviceToken.fcm_token == fcm_token)
            .one_or_none()
        )
        if not row:
            return
        row.is_active = False
        row.updated_at = datetime.utcnow()
