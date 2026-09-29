"""Publish admin-scheduled draft Issues whose time has arrived."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.admin_issue_service import AdminIssueService

logger = logging.getLogger(__name__)


def run_publish_scheduled(db: Session, *, limit: int = 50) -> dict:
    published = AdminIssueService(db).publish_due(limit=limit)
    if published:
        logger.info("scheduled publish due published=%s", published)
    return {"published": published}
