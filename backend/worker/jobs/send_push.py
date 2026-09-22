"""Worker job: deliver pending push_notifications via FCM."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.push_send_service import send_pending_pushes

logger = logging.getLogger(__name__)


def run_pending_push(db: Session, *, limit: int = 50) -> dict:
    result = send_pending_pushes(db, limit=limit)
    logger.info("pending_push %s", result)
    return result
