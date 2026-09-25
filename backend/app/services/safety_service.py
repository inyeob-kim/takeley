"""Report / hide / block / eject for anonymous UGC (App Store 1.2)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import (
    ContentReport,
    HiddenContent,
    IssueComment,
    IssueTake,
    User,
    UserBlock,
)
from app.schemas import ContentReportOut, SafetyOkOut
from app.services.contributor_service import require_active_user

_REASONS = {"hate", "sexual", "violence", "spam", "other"}
_TARGET_TYPES = {"comment", "take"}


class SafetyError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def blocked_user_ids(db: Session, viewer_id: str | None) -> set[str]:
    if not viewer_id:
        return set()
    rows = db.query(UserBlock.blocked_id).filter(UserBlock.blocker_id == viewer_id).all()
    return {row[0] for row in rows}


def hidden_target_ids(
    db: Session, viewer_id: str | None, *, target_type: str
) -> set[str]:
    if not viewer_id:
        return set()
    rows = (
        db.query(HiddenContent.target_id)
        .filter(
            HiddenContent.user_id == viewer_id,
            HiddenContent.target_type == target_type,
        )
        .all()
    )
    return {row[0] for row in rows}


def _hide(db: Session, *, user_id: str, target_type: str, target_id: str) -> None:
    exists = (
        db.query(HiddenContent)
        .filter(
            HiddenContent.user_id == user_id,
            HiddenContent.target_type == target_type,
            HiddenContent.target_id == target_id,
        )
        .first()
    )
    if exists:
        return
    db.add(
        HiddenContent(user_id=user_id, target_type=target_type, target_id=target_id)
    )


def _resolve_target(
    db: Session, *, target_type: str, target_id: str
) -> tuple[str, str]:
    if target_type == "comment":
        row = db.query(IssueComment).filter(IssueComment.id == target_id).first()
        if not row or row.status == "removed":
            raise SafetyError("content_not_found", status_code=404)
        return row.user_id, row.id
    row = db.query(IssueTake).filter(IssueTake.id == target_id).first()
    if not row:
        raise SafetyError("content_not_found", status_code=404)
    return row.author_id, row.id


class SafetyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def report(
        self,
        *,
        user_id: str,
        target_type: str,
        target_id: str,
        reason: str,
        details: str | None = None,
    ) -> SafetyOkOut:
        user = require_active_user(self.db, user_id)
        if target_type not in _TARGET_TYPES:
            raise SafetyError("invalid_target")
        if reason not in _REASONS:
            raise SafetyError("invalid_reason")
        author_id, resolved_id = _resolve_target(
            self.db, target_type=target_type, target_id=target_id
        )
        if author_id == user.id:
            raise SafetyError("cannot_report_own")
        existing = (
            self.db.query(ContentReport)
            .filter(
                ContentReport.reporter_id == user.id,
                ContentReport.target_type == target_type,
                ContentReport.target_id == resolved_id,
                ContentReport.status == "open",
            )
            .first()
        )
        if not existing:
            self.db.add(
                ContentReport(
                    reporter_id=user.id,
                    target_type=target_type,
                    target_id=resolved_id,
                    target_user_id=author_id,
                    reason=reason,
                    details=(details or "").strip()[:500] or None,
                )
            )
        _hide(
            self.db,
            user_id=user.id,
            target_type=target_type,
            target_id=resolved_id,
        )
        self.db.commit()
        return SafetyOkOut()

    def hide(
        self, *, user_id: str, target_type: str, target_id: str
    ) -> SafetyOkOut:
        user = require_active_user(self.db, user_id)
        if target_type not in _TARGET_TYPES:
            raise SafetyError("invalid_target")
        _resolve_target(self.db, target_type=target_type, target_id=target_id)
        _hide(
            self.db,
            user_id=user.id,
            target_type=target_type,
            target_id=target_id,
        )
        self.db.commit()
        return SafetyOkOut()

    def delete_own_comment(self, *, user_id: str, comment_id: str) -> SafetyOkOut:
        user = require_active_user(self.db, user_id)
        row = self.db.query(IssueComment).filter(IssueComment.id == comment_id).first()
        if not row or row.status == "removed":
            raise SafetyError("content_not_found", status_code=404)
        if row.user_id != user.id:
            raise SafetyError("not_author", status_code=403)
        row.status = "removed"
        self.db.commit()
        return SafetyOkOut()

    def block_user(self, *, user_id: str, blocked_user_id: str) -> SafetyOkOut:
        user = require_active_user(self.db, user_id)
        blocked_id = (blocked_user_id or "").strip()
        if not blocked_id or blocked_id == user.id:
            raise SafetyError("invalid_user")
        exists = (
            self.db.query(UserBlock)
            .filter(
                UserBlock.blocker_id == user.id,
                UserBlock.blocked_id == blocked_id,
            )
            .first()
        )
        if not exists:
            self.db.add(UserBlock(blocker_id=user.id, blocked_id=blocked_id))
        self.db.commit()
        return SafetyOkOut()

    def list_reports(self, *, status: str = "open", limit: int = 50) -> list[ContentReportOut]:
        limit = max(1, min(limit, 100))
        if status not in {"open", "removed", "dismissed"}:
            raise SafetyError("invalid_status")
        rows = (
            self.db.query(ContentReport)
            .filter(ContentReport.status == status)
            .order_by(ContentReport.created_at.asc())
            .limit(limit)
            .all()
        )
        return [_report_out(self.db, row) for row in rows]

    def resolve(
        self,
        report_id: str,
        *,
        action: str,
        eject: bool = False,
    ) -> ContentReportOut:
        if action not in {"remove", "dismiss"}:
            raise SafetyError("invalid_action")
        row = (
            self.db.query(ContentReport)
            .filter(ContentReport.id == report_id)
            .first()
        )
        if not row:
            raise SafetyError("report_not_found", status_code=404)
        if row.status != "open":
            return _report_out(self.db, row)
        if action == "remove":
            _remove_target(self.db, row)
            if eject:
                _eject_user(self.db, row.target_user_id)
            row.status = "removed"
        else:
            row.status = "dismissed"
        row.resolved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return _report_out(self.db, row)


def _remove_target(db: Session, row: ContentReport) -> None:
    if row.target_type == "comment":
        comment = (
            db.query(IssueComment).filter(IssueComment.id == row.target_id).first()
        )
        if comment:
            comment.status = "removed"
        return
    take = db.query(IssueTake).filter(IssueTake.id == row.target_id).first()
    if take and take.status == "published":
        take.status = "rejected"
        take.admin_note = "ugc_report"
        take.updated_at = datetime.utcnow()


def _eject_user(db: Session, user_id: str) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
    user.status = "suspended"
    if user.contributor_status == "APPROVED":
        user.contributor_status = "SUSPENDED"
    db.query(IssueComment).filter(
        IssueComment.user_id == user_id,
        IssueComment.status == "visible",
    ).update({IssueComment.status: "removed"}, synchronize_session=False)
    now = datetime.utcnow()
    db.query(IssueTake).filter(
        IssueTake.author_id == user_id,
        IssueTake.status == "published",
    ).update(
        {
            IssueTake.status: "rejected",
            IssueTake.admin_note: "ugc_eject",
            IssueTake.updated_at: now,
        },
        synchronize_session=False,
    )


def _preview(db: Session, row: ContentReport) -> str:
    if row.target_type == "comment":
        comment = (
            db.query(IssueComment).filter(IssueComment.id == row.target_id).first()
        )
        return (comment.content if comment else "")[:160]
    take = db.query(IssueTake).filter(IssueTake.id == row.target_id).first()
    if not take:
        return ""
    return (take.title or take.body or "")[:160]


def _report_out(db: Session, row: ContentReport) -> ContentReportOut:
    return ContentReportOut(
        id=row.id,
        reporter_id=row.reporter_id,
        target_type=row.target_type,
        target_id=row.target_id,
        target_user_id=row.target_user_id,
        reason=row.reason,
        details=row.details,
        status=row.status,
        preview=_preview(db, row),
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )
