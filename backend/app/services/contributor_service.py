"""Contributor permission helpers and application service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import ContributorApplication, IssueUserEvent, User
from app.schemas import (
    ContributorApplicationOut,
    ContributorMeOut,
)


class ContributorError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def require_active_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ContributorError("User not found", status_code=404)
    if (user.status or "").lower() != "active":
        raise ContributorError("User inactive", status_code=403)
    return user


def require_approved_contributor(db: Session, user_id: str) -> User:
    user = require_active_user(db, user_id)
    if user.contributor_status != "APPROVED":
        raise ContributorError("Contributor permission required", status_code=403)
    return user


def _append_contributor_event(
    db: Session,
    *,
    user_id: str,
    event: str,
    signal_id: str | None = None,
    take_id: str | None = None,
) -> None:
    db.add(
        IssueUserEvent(
            user_id=user_id,
            signal_id=signal_id,
            take_id=take_id,
            event=event,
            created_at=datetime.utcnow(),
        )
    )


def _application_out(
    app: ContributorApplication, *, contributor_status: str
) -> ContributorApplicationOut:
    return ContributorApplicationOut(
        id=app.id,
        user_id=app.user_id,
        motivation=app.motivation or "",
        interests=app.interests or "",
        sample_text=app.sample_text or "",
        status=app.status,
        admin_note=app.admin_note,
        created_at=app.created_at,
        updated_at=app.updated_at,
        reviewed_at=app.reviewed_at,
        contributor_status=contributor_status,
    )


class ContributorService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_me(self, user_id: str) -> ContributorMeOut:
        user = require_active_user(self.db, user_id)
        app = (
            self.db.query(ContributorApplication)
            .filter(ContributorApplication.user_id == user.id)
            .order_by(ContributorApplication.created_at.desc())
            .first()
        )
        return ContributorMeOut(
            user_id=user.id,
            contributor_status=user.contributor_status or "NONE",
            display_name=user.display_name,
            contributor_approved_at=user.contributor_approved_at,
            application=(
                _application_out(app, contributor_status=user.contributor_status)
                if app
                else None
            ),
        )

    def apply(
        self,
        user_id: str,
        *,
        motivation: str,
        interests: str,
        sample_text: str,
    ) -> ContributorApplicationOut:
        user = require_active_user(self.db, user_id)
        status = user.contributor_status or "NONE"
        if status == "PENDING":
            raise ContributorError("Application already pending", status_code=409)
        if status == "APPROVED":
            raise ContributorError("Already an approved contributor", status_code=409)
        if status == "SUSPENDED":
            raise ContributorError("Contributor suspended", status_code=403)
        # NONE and REJECTED may apply (reapply after reject is explicit policy).
        if status not in ("NONE", "REJECTED"):
            raise ContributorError("Cannot apply in current status", status_code=409)

        pending = (
            self.db.query(ContributorApplication)
            .filter(
                ContributorApplication.user_id == user.id,
                ContributorApplication.status == "PENDING",
            )
            .first()
        )
        if pending:
            raise ContributorError("Application already pending", status_code=409)

        app = ContributorApplication(
            user_id=user.id,
            motivation=motivation.strip(),
            interests=interests.strip(),
            sample_text=sample_text.strip(),
            status="PENDING",
        )
        user.contributor_status = "PENDING"
        self.db.add(app)
        _append_contributor_event(
            self.db, user_id=user.id, event="contributor_apply"
        )
        self.db.commit()
        self.db.refresh(app)
        self.db.refresh(user)
        return _application_out(app, contributor_status=user.contributor_status)

    def list_applications(
        self, *, status: str = "PENDING", limit: int = 50
    ) -> list[ContributorApplicationOut]:
        limit = max(1, min(limit, 100))
        rows = (
            self.db.query(ContributorApplication)
            .filter(ContributorApplication.status == status)
            .order_by(ContributorApplication.created_at.asc())
            .limit(limit)
            .all()
        )
        out: list[ContributorApplicationOut] = []
        for app in rows:
            user = self.db.query(User).filter(User.id == app.user_id).first()
            cs = (user.contributor_status if user else "NONE") or "NONE"
            out.append(_application_out(app, contributor_status=cs))
        return out

    def approve_application(self, application_id: str) -> ContributorApplicationOut:
        app = (
            self.db.query(ContributorApplication)
            .filter(ContributorApplication.id == application_id)
            .first()
        )
        if not app:
            raise ContributorError("Application not found", status_code=404)
        if app.status != "PENDING":
            raise ContributorError("Application not pending", status_code=409)
        user = require_active_user(self.db, app.user_id)
        now = datetime.utcnow()
        app.status = "APPROVED"
        app.reviewed_at = now
        app.updated_at = now
        user.contributor_status = "APPROVED"
        user.contributor_approved_at = now
        _append_contributor_event(
            self.db, user_id=user.id, event="contributor_approved"
        )
        self.db.commit()
        self.db.refresh(app)
        self.db.refresh(user)
        return _application_out(app, contributor_status=user.contributor_status)

    def reject_application(
        self, application_id: str, *, reason: str | None = None
    ) -> ContributorApplicationOut:
        app = (
            self.db.query(ContributorApplication)
            .filter(ContributorApplication.id == application_id)
            .first()
        )
        if not app:
            raise ContributorError("Application not found", status_code=404)
        if app.status != "PENDING":
            raise ContributorError("Application not pending", status_code=409)
        user = require_active_user(self.db, app.user_id)
        now = datetime.utcnow()
        app.status = "REJECTED"
        app.reviewed_at = now
        app.updated_at = now
        if reason:
            app.admin_note = reason.strip()[:500]
        user.contributor_status = "REJECTED"
        self.db.commit()
        self.db.refresh(app)
        self.db.refresh(user)
        return _application_out(app, contributor_status=user.contributor_status)

    def suspend_contributor(
        self, application_id: str, *, reason: str | None = None
    ) -> ContributorApplicationOut:
        """Revoke writing rights: APPROVED user → SUSPENDED. Published takes stay."""
        app = (
            self.db.query(ContributorApplication)
            .filter(ContributorApplication.id == application_id)
            .first()
        )
        if not app:
            raise ContributorError("Application not found", status_code=404)
        if app.status != "APPROVED":
            raise ContributorError(
                "Only approved applications can suspend", status_code=409
            )
        user = require_active_user(self.db, app.user_id)
        if user.contributor_status == "SUSPENDED":
            return _application_out(app, contributor_status=user.contributor_status)
        if user.contributor_status != "APPROVED":
            raise ContributorError(
                "Only approved contributors can be suspended", status_code=409
            )
        now = datetime.utcnow()
        user.contributor_status = "SUSPENDED"
        app.updated_at = now
        if reason:
            app.admin_note = reason.strip()[:500]
        _append_contributor_event(
            self.db, user_id=user.id, event="contributor_suspended"
        )
        self.db.commit()
        self.db.refresh(app)
        self.db.refresh(user)
        return _application_out(app, contributor_status=user.contributor_status)

    def reinstate_contributor(
        self, application_id: str
    ) -> ContributorApplicationOut:
        """Restore writing rights: SUSPENDED → APPROVED."""
        app = (
            self.db.query(ContributorApplication)
            .filter(ContributorApplication.id == application_id)
            .first()
        )
        if not app:
            raise ContributorError("Application not found", status_code=404)
        if app.status != "APPROVED":
            raise ContributorError(
                "Only approved applications can reinstate", status_code=409
            )
        user = require_active_user(self.db, app.user_id)
        if user.contributor_status == "APPROVED":
            return _application_out(app, contributor_status=user.contributor_status)
        if user.contributor_status != "SUSPENDED":
            raise ContributorError(
                "Only suspended contributors can be reinstated", status_code=409
            )
        now = datetime.utcnow()
        user.contributor_status = "APPROVED"
        if not user.contributor_approved_at:
            user.contributor_approved_at = now
        app.updated_at = now
        _append_contributor_event(
            self.db, user_id=user.id, event="contributor_reinstated"
        )
        self.db.commit()
        self.db.refresh(app)
        self.db.refresh(user)
        return _application_out(app, contributor_status=user.contributor_status)
