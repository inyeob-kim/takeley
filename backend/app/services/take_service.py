"""IssueTake service — deep thoughts bound to Issues (Gate 2 content lifecycle)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import IssueTake, IssueTakeReaction, Signal, User
from app.schemas import (
    ContributorStatsOut,
    IssueTakeListOut,
    IssueTakeOut,
    IssueTakePublicOut,
    IssueTakeReactionOut,
    MyDeepThoughtOut,
)
from app.services.contributor_service import (
    ContributorError,
    require_active_user,
    require_approved_contributor,
)
from app.services.issue_service import _append_user_event


def _normalize_urls(urls: list[str] | None) -> list[str]:
    if not urls:
        return []
    out: list[str] = []
    for u in urls[:10]:
        s = (u or "").strip()
        if not s:
            continue
        if len(s) > 1024:
            raise ContributorError("source_url too long", status_code=400)
        out.append(s)
    return out


def _display_name(user: User | None) -> str | None:
    if not user:
        return None
    name = (user.display_name or "").strip()
    return name or None


def _take_out(
    take: IssueTake,
    *,
    author: User | None = None,
    include_admin_note: bool = False,
) -> IssueTakeOut:
    return IssueTakeOut(
        id=take.id,
        issue_id=take.issue_id,
        author_id=take.author_id,
        display_name=_display_name(author),
        title=take.title,
        body=take.body or "",
        source_urls=list(take.source_urls or []),
        status=take.status,
        view_count=int(take.view_count or 0),
        reaction_count=int(take.reaction_count or 0),
        created_at=take.created_at,
        updated_at=take.updated_at,
        published_at=take.published_at,
        admin_note=take.admin_note if include_admin_note else None,
    )


def _public_out(take: IssueTake, *, author: User | None = None) -> IssueTakePublicOut:
    return IssueTakePublicOut(
        id=take.id,
        issue_id=take.issue_id,
        author_id=take.author_id,
        display_name=_display_name(author),
        title=take.title,
        body=take.body or "",
        source_urls=list(take.source_urls or []),
        status=take.status,
        view_count=int(take.view_count or 0),
        reaction_count=int(take.reaction_count or 0),
        published_at=take.published_at,
        created_at=take.created_at,
    )


def _require_published_issue(db: Session, issue_id: str) -> Signal:
    issue = (
        db.query(Signal)
        .filter(Signal.id == issue_id, Signal.status == "published")
        .first()
    )
    if not issue:
        raise ContributorError("Issue not found", status_code=404)
    return issue


def _get_take(db: Session, take_id: str) -> IssueTake:
    take = db.query(IssueTake).filter(IssueTake.id == take_id).first()
    if not take:
        raise ContributorError("IssueTake not found", status_code=404)
    return take


def _require_take_on_issue(db: Session, issue_id: str, take_id: str) -> IssueTake:
    take = _get_take(db, take_id)
    if take.issue_id != issue_id:
        raise ContributorError("IssueTake does not belong to Issue", status_code=404)
    return take


class TakeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        issue_id: str,
        *,
        user_id: str,
        title: str,
        body: str,
        source_urls: list[str] | None = None,
        body_issue_id: str | None = None,
    ) -> IssueTakeOut:
        if body_issue_id is not None and body_issue_id != issue_id:
            raise ContributorError("issue_id mismatch", status_code=400)
        user = require_approved_contributor(self.db, user_id)
        _require_published_issue(self.db, issue_id)
        from app.services.content_moderation import (
            ObjectionableContent,
            reject_objectionable,
        )

        try:
            reject_objectionable(title, body)
        except ObjectionableContent as exc:
            raise ContributorError(str(exc), status_code=400) from exc
        take = IssueTake(
            issue_id=issue_id,
            author_id=user.id,
            title=title.strip(),
            body=body.strip(),
            source_urls=_normalize_urls(source_urls),
            status="draft",
            view_count=0,
            reaction_count=0,
        )
        self.db.add(take)
        self.db.commit()
        self.db.refresh(take)
        return _take_out(take, author=user, include_admin_note=True)

    def update(
        self,
        issue_id: str,
        take_id: str,
        *,
        user_id: str,
        title: str | None = None,
        body: str | None = None,
        source_urls: list[str] | None = None,
    ) -> IssueTakeOut:
        user = require_approved_contributor(self.db, user_id)
        take = _require_take_on_issue(self.db, issue_id, take_id)
        if take.author_id != user.id:
            raise ContributorError("Not the author", status_code=403)
        if take.status == "pending_review":
            raise ContributorError("Cannot edit while pending review", status_code=409)
        if take.status == "published":
            raise ContributorError("Cannot edit published take", status_code=409)
        if take.status == "rejected":
            # Explicit: rejected → draft on revision start.
            take.status = "draft"
            take.admin_note = take.admin_note  # preserve
        elif take.status != "draft":
            raise ContributorError("Invalid status for edit", status_code=409)
        if title is not None:
            take.title = title.strip()
        if body is not None:
            take.body = body.strip()
        from app.services.content_moderation import (
            ObjectionableContent,
            reject_objectionable,
        )

        try:
            reject_objectionable(take.title, take.body)
        except ObjectionableContent as exc:
            raise ContributorError(str(exc), status_code=400) from exc
        if source_urls is not None:
            take.source_urls = _normalize_urls(source_urls)
        take.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(take)
        return _take_out(take, author=user, include_admin_note=True)

    def submit(self, issue_id: str, take_id: str, *, user_id: str) -> IssueTakeOut:
        user = require_approved_contributor(self.db, user_id)
        take = _require_take_on_issue(self.db, issue_id, take_id)
        if take.author_id != user.id:
            raise ContributorError("Not the author", status_code=403)
        if take.status != "draft":
            raise ContributorError("Only draft can be submitted", status_code=409)
        if not (take.title or "").strip() or not (take.body or "").strip():
            raise ContributorError("title and body required", status_code=400)
        take.status = "pending_review"
        take.updated_at = datetime.utcnow()
        _append_user_event(
            self.db,
            user_id=user.id,
            signal_id=take.issue_id,
            event="take_submit",
            take_id=take.id,
        )
        self.db.commit()
        self.db.refresh(take)
        return _take_out(take, author=user, include_admin_note=True)

    def withdraw(self, issue_id: str, take_id: str, *, user_id: str) -> IssueTakeOut:
        user = require_approved_contributor(self.db, user_id)
        take = _require_take_on_issue(self.db, issue_id, take_id)
        if take.author_id != user.id:
            raise ContributorError("Not the author", status_code=403)
        if take.status != "pending_review":
            raise ContributorError("Only pending_review can be withdrawn", status_code=409)
        take.status = "draft"
        take.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(take)
        return _take_out(take, author=user, include_admin_note=True)

    def get_for_reader(
        self,
        issue_id: str,
        take_id: str,
        *,
        user_id: str | None = None,
        record_view: bool = True,
    ) -> IssueTakePublicOut | IssueTakeOut:
        take = _require_take_on_issue(self.db, issue_id, take_id)
        author = self.db.query(User).filter(User.id == take.author_id).first()
        is_author = bool(user_id and take.author_id == user_id)
        if take.status == "published":
            if record_view:
                take.view_count = int(take.view_count or 0) + 1
                uid = user_id or "anonymous"
                _append_user_event(
                    self.db,
                    user_id=uid,
                    signal_id=take.issue_id,
                    event="take_open",
                    take_id=take.id,
                )
                self.db.commit()
                self.db.refresh(take)
            return _public_out(take, author=author)
        if is_author:
            return _take_out(take, author=author, include_admin_note=True)
        raise ContributorError("IssueTake not found", status_code=404)

    def list_published(
        self, issue_id: str, *, user_id: str | None = None, limit: int = 20
    ) -> IssueTakeListOut:
        from app.services.safety_service import blocked_user_ids, hidden_target_ids

        _require_published_issue(self.db, issue_id)
        limit = max(1, min(limit, 50))
        blocked = blocked_user_ids(self.db, user_id)
        hidden = hidden_target_ids(self.db, user_id, target_type="take")
        query = self.db.query(IssueTake).filter(
            IssueTake.issue_id == issue_id,
            IssueTake.status == "published",
        )
        if blocked:
            query = query.filter(~IssueTake.author_id.in_(blocked))
        if hidden:
            query = query.filter(~IssueTake.id.in_(hidden))
        rows = (
            query.order_by(IssueTake.published_at.desc(), IssueTake.created_at.desc())
            .limit(limit)
            .all()
        )
        authors = {
            u.id: u
            for u in self.db.query(User)
            .filter(User.id.in_([r.author_id for r in rows] or ["__none__"]))
            .all()
        }
        items = [_public_out(r, author=authors.get(r.author_id)) for r in rows]
        return IssueTakeListOut(items=items, count=len(items))

    def list_mine(self, issue_id: str, *, user_id: str) -> list[IssueTakeOut]:
        user = require_active_user(self.db, user_id)
        rows = (
            self.db.query(IssueTake)
            .filter(
                IssueTake.issue_id == issue_id,
                IssueTake.author_id == user.id,
            )
            .order_by(IssueTake.updated_at.desc())
            .all()
        )
        return [_take_out(r, author=user, include_admin_note=True) for r in rows]

    def add_reaction(
        self, issue_id: str, take_id: str, *, user_id: str
    ) -> IssueTakeReactionOut:
        user = require_active_user(self.db, user_id)
        take = _require_take_on_issue(self.db, issue_id, take_id)
        if take.status != "published":
            raise ContributorError("Only published takes accept reactions", status_code=409)
        existing = (
            self.db.query(IssueTakeReaction)
            .filter(
                IssueTakeReaction.take_id == take.id,
                IssueTakeReaction.user_id == user.id,
            )
            .first()
        )
        if existing:
            return IssueTakeReactionOut(
                ok=True,
                take_id=take.id,
                reaction_count=int(take.reaction_count or 0),
                already_reacted=True,
            )
        self.db.add(
            IssueTakeReaction(
                take_id=take.id,
                user_id=user.id,
                created_at=datetime.utcnow(),
            )
        )
        take.reaction_count = int(take.reaction_count or 0) + 1
        _append_user_event(
            self.db,
            user_id=user.id,
            signal_id=take.issue_id,
            event="take_react",
            take_id=take.id,
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            take = _require_take_on_issue(self.db, issue_id, take_id)
            return IssueTakeReactionOut(
                ok=True,
                take_id=take.id,
                reaction_count=int(take.reaction_count or 0),
                already_reacted=True,
            )
        self.db.refresh(take)
        return IssueTakeReactionOut(
            ok=True,
            take_id=take.id,
            reaction_count=int(take.reaction_count or 0),
            already_reacted=False,
        )

    # --- Admin ---

    def admin_list(
        self, *, status: str = "pending_review", limit: int = 50
    ) -> list[IssueTakeOut]:
        limit = max(1, min(limit, 100))
        rows = (
            self.db.query(IssueTake)
            .filter(IssueTake.status == status)
            .order_by(IssueTake.updated_at.asc())
            .limit(limit)
            .all()
        )
        authors = {
            u.id: u
            for u in self.db.query(User)
            .filter(User.id.in_([r.author_id for r in rows] or ["__none__"]))
            .all()
        }
        return [
            _take_out(r, author=authors.get(r.author_id), include_admin_note=True)
            for r in rows
        ]

    def admin_publish(self, take_id: str) -> IssueTakeOut:
        take = _get_take(self.db, take_id)
        if take.status != "pending_review":
            raise ContributorError("Only pending_review can be published", status_code=409)
        now = datetime.utcnow()
        take.status = "published"
        take.published_at = now
        take.updated_at = now
        author = self.db.query(User).filter(User.id == take.author_id).first()
        _append_user_event(
            self.db,
            user_id=take.author_id,
            signal_id=take.issue_id,
            event="take_published",
            take_id=take.id,
        )
        self.db.commit()
        self.db.refresh(take)
        return _take_out(take, author=author, include_admin_note=True)

    def admin_reject(self, take_id: str, *, reason: str | None = None) -> IssueTakeOut:
        take = _get_take(self.db, take_id)
        if take.status not in ("pending_review", "published"):
            raise ContributorError(
                "Only pending_review or published can be rejected", status_code=409
            )
        take.status = "rejected"
        take.updated_at = datetime.utcnow()
        if reason:
            take.admin_note = reason.strip()[:500]
        author = self.db.query(User).filter(User.id == take.author_id).first()
        self.db.commit()
        self.db.refresh(take)
        return _take_out(take, author=author, include_admin_note=True)

    def admin_unpublish(self, take_id: str, *, reason: str | None = None) -> IssueTakeOut:
        """published → rejected (explicit unpublish policy for MVP)."""
        take = _get_take(self.db, take_id)
        if take.status != "published":
            raise ContributorError("Only published can be unpublished", status_code=409)
        take.status = "rejected"
        take.updated_at = datetime.utcnow()
        if reason:
            take.admin_note = reason.strip()[:500]
        else:
            take.admin_note = take.admin_note or "unpublished"
        author = self.db.query(User).filter(User.id == take.author_id).first()
        self.db.commit()
        self.db.refresh(take)
        return _take_out(take, author=author, include_admin_note=True)


def build_contributor_activity(
    db: Session, user_id: str, *, limit: int = 20
) -> tuple[ContributorStatsOut | None, list[MyDeepThoughtOut]]:
    """Additive Activity fields — only when contributor_status == APPROVED."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.contributor_status != "APPROVED":
        return None, []
    limit = max(1, min(limit, 50))
    takes = (
        db.query(IssueTake)
        .filter(IssueTake.author_id == user.id)
        .order_by(IssueTake.updated_at.desc())
        .limit(limit)
        .all()
    )
    issue_ids = list({t.issue_id for t in takes})
    titles = {
        s.id: s.title
        for s in db.query(Signal).filter(Signal.id.in_(issue_ids or ["__none__"])).all()
    }
    agg = (
        db.query(
            func.count(IssueTake.id),
            func.coalesce(func.sum(IssueTake.view_count), 0),
            func.coalesce(func.sum(IssueTake.reaction_count), 0),
        )
        .filter(IssueTake.author_id == user.id)
        .one()
    )
    stats = ContributorStatsOut(
        takes_count=int(agg[0] or 0),
        total_views=int(agg[1] or 0),
        total_reactions=int(agg[2] or 0),
    )
    deep = [
        MyDeepThoughtOut(
            id=t.id,
            issue_id=t.issue_id,
            issue_title=titles.get(t.issue_id, ""),
            title=t.title,
            status=t.status,
            view_count=int(t.view_count or 0),
            reaction_count=int(t.reaction_count or 0),
            created_at=t.created_at,
            updated_at=t.updated_at,
            published_at=t.published_at,
        )
        for t in takes
    ]
    return stats, deep
