"""Worker-only FCM send for pending push_notifications rows."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import DeviceToken, PushNotification, PushNotificationLog
from app.services.push_token_service import PushTokenService

logger = logging.getLogger(__name__)

_firebase_app = None
_firebase_init_attempted = False


def _init_firebase() -> Any | None:
    global _firebase_app, _firebase_init_attempted
    if _firebase_init_attempted:
        return _firebase_app
    _firebase_init_attempted = True
    settings = get_settings()
    if not settings.fcm_enabled:
        logger.info("fcm disabled (FCM_ENABLED=false)")
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        logger.warning("fcm skip reason=firebase_admin_not_installed")
        return None
    if not settings.firebase_credentials_path:
        logger.warning("fcm skip reason=no_credentials_path")
        return None
    cred_path = Path(settings.firebase_credentials_path)
    if not cred_path.is_absolute():
        cred_path = Path(__file__).resolve().parents[2] / cred_path
    if not cred_path.exists():
        logger.warning("fcm skip reason=credentials_missing path=%s", cred_path)
        return None
    try:
        try:
            _firebase_app = firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(str(cred_path))
            _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("fcm ready")
        return _firebase_app
    except Exception:
        logger.exception("fcm init failed")
        _firebase_app = None
        return None


def _stringify_data(data: dict | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (data or {}).items():
        if value is None:
            continue
        out[str(key)] = value if isinstance(value, str) else str(value)
    return out


def _send_multicast(
    *,
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str],
) -> list[tuple[str, str, str | None, str | None]]:
    """
    Returns list of (token, status, error_code, error_message)
    status: success | failed | expired_token
    """
    if not tokens:
        return []
    if _init_firebase() is None:
        return [
            (t, "failed", "fcm_unavailable", "FCM not configured")
            for t in tokens
        ]
    from firebase_admin import messaging

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data,
        tokens=tokens,
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            headers={"apns-priority": "10"},
            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
        ),
    )
    response = messaging.send_each_for_multicast(message)
    results: list[tuple[str, str, str | None, str | None]] = []
    for token, send_resp in zip(tokens, response.responses):
        if send_resp.success:
            results.append((token, "success", None, None))
            continue
        exc = send_resp.exception
        code = getattr(exc, "code", None) or type(exc).__name__
        msg = str(exc) if exc else "unknown"
        expired = "registration-token-not-registered" in msg.lower() or (
            str(code).lower() in {"not-found", "invalid-argument", "unregistered"}
        )
        results.append(
            (token, "expired_token" if expired else "failed", str(code), msg)
        )
    return results


def send_pending_pushes(db: Session, *, limit: int = 50) -> dict:
    now = datetime.utcnow()
    rows = (
        db.query(PushNotification)
        .filter(
            PushNotification.status == "pending",
            PushNotification.scheduled_at <= now,
        )
        .order_by(PushNotification.scheduled_at.asc())
        .limit(limit)
        .all()
    )
    sent = 0
    failed = 0
    skipped = 0
    token_svc = PushTokenService(db)

    for row in rows:
        tokens = token_svc.list_active(row.user_id)
        if not tokens:
            row.status = "cancelled"
            row.error_message = "no_active_token"
            failed += 1
            db.commit()
            continue

        data = _stringify_data(row.data)
        data.setdefault("notification_id", row.id)
        data.setdefault("category", row.category)
        outcomes = _send_multicast(
            tokens=[t.fcm_token for t in tokens],
            title=row.title,
            body=row.body,
            data=data,
        )
        any_success = False
        for token, status, err_code, err_msg in outcomes:
            platform = next(
                (t.platform for t in tokens if t.fcm_token == token),
                "web",
            )
            db.add(
                PushNotificationLog(
                    notification_id=row.id,
                    user_id=row.user_id,
                    fcm_token=token[:32] + "…",
                    platform=platform,
                    status=status,
                    error_code=err_code,
                    error_message=(err_msg or "")[:500] or None,
                )
            )
            if status == "success":
                any_success = True
            elif status == "expired_token":
                token_svc.deactivate_token(token)

        if any_success:
            row.status = "sent"
            row.sent_at = datetime.utcnow()
            row.error_message = None
            sent += 1
        else:
            row.retry_count = int(row.retry_count or 0) + 1
            if row.retry_count >= int(row.max_retries or 3):
                row.status = "failed"
                row.error_message = "max_retries"
                failed += 1
            else:
                row.scheduled_at = datetime.utcnow() + timedelta(minutes=1)
                skipped += 1
        db.commit()

    result = {
        "pending_seen": len(rows),
        "sent": sent,
        "failed": failed,
        "retried": skipped,
    }
    logger.info("send_pending_push %s", result)
    return result
