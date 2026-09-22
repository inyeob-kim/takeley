"""Admin review: draft Issues → publish / reject (not used by consumer app)."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.core.usage import ISSUE_PUBLISHED, record_usage
from app.db.models import Signal
from app.domain.models import SignalStatus
from app.pipeline.industries import normalize_industry_category
from app.schemas import IssueListOut, IssueOut
from app.services.issue_image_service import (
    delete_local_image_if_owned,
    normalize_image_url,
    save_issue_image,
)
from app.services.issue_service import (
    _to_issue_out,
    replace_participation_options,
    touch_content_updated,
)
from app.services.push_enqueue_service import enqueue_signal_new
from fastapi import UploadFile

logger = logging.getLogger(__name__)


class AdminIssueService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_status(
        self, *, status: str = "draft", limit: int = 50
    ) -> IssueListOut:
        limit = max(1, min(limit, 100))
        status = (status or "draft").strip().lower()
        allowed = {"draft", "published", "rejected"}
        if status not in allowed:
            status = "draft"
        rows = (
            self.db.query(Signal)
            .options(
                joinedload(Signal.participation_options),
                joinedload(Signal.sources),
            )
            .filter(Signal.status == status)
            .order_by(Signal.first_seen_at.desc())
            .limit(limit)
            .all()
        )
        items = [
            _to_issue_out(
                self.db, s, include_sources=False, expose_sources=True
            )
            for s in rows
        ]
        return IssueListOut(items=items, count=len(items))

    def get(self, issue_id: str) -> IssueOut | None:
        row = (
            self.db.query(Signal)
            .options(
                joinedload(Signal.participation_options),
                joinedload(Signal.sources),
            )
            .filter(Signal.id == issue_id)
            .first()
        )
        if not row:
            return None
        return _to_issue_out(
            self.db, row, include_sources=True, expose_sources=True
        )

    def update(
        self,
        issue_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        why_it_matters: str | None = None,
        column_body: str | None = None,
        column_author_name: str | None = None,
        column_author_image_url: str | None = None,
        clear_column_author_image: bool = False,
        image_url: str | None = None,
        clear_image: bool = False,
        key_points: list[str] | None = None,
        category: str | None = None,
        participation_suitable: bool | None = None,
        participation_question: str | None = None,
        participation_options: list[str] | None = None,
        show_sources: bool | None = None,
        push_title: str | None = None,
        push_body: str | None = None,
    ) -> IssueOut | None:
        row = (
            self.db.query(Signal)
            .options(joinedload(Signal.participation_options))
            .filter(Signal.id == issue_id)
            .first()
        )
        if not row:
            return None
        if row.status == SignalStatus.REJECTED.value:
            raise ValueError("rejected_issue_cannot_edit")
        if row.status == SignalStatus.PUBLISHED.value:
            raise ValueError("published_issue_cannot_edit")

        content_changed = False

        if title is not None:
            t = title.strip()
            if len(t) < 4:
                raise ValueError("title_too_short")
            row.title = t[:512]
            content_changed = True
        if summary is not None:
            s = summary.strip()
            if len(s) < 8:
                raise ValueError("summary_too_short")
            row.summary = s
            content_changed = True
        if why_it_matters is not None:
            row.why_it_matters = why_it_matters.strip()
            content_changed = True
        if column_body is not None:
            row.column_body = column_body.strip()
            content_changed = True
        if column_author_name is not None:
            name = column_author_name.strip()
            row.column_author_name = name[:128] if name else None
            content_changed = True
        if clear_column_author_image:
            delete_local_image_if_owned(
                getattr(row, "column_author_image_url", None)
            )
            row.column_author_image_url = None
            content_changed = True
        elif column_author_image_url is not None:
            next_author = normalize_image_url(column_author_image_url)
            if next_author != (row.column_author_image_url or None):
                delete_local_image_if_owned(
                    getattr(row, "column_author_image_url", None)
                )
                content_changed = True
            row.column_author_image_url = next_author
        if clear_image:
            delete_local_image_if_owned(getattr(row, "image_url", None))
            row.image_url = None
            content_changed = True
        elif image_url is not None:
            next_url = normalize_image_url(image_url)
            if next_url != (row.image_url or None):
                delete_local_image_if_owned(getattr(row, "image_url", None))
                content_changed = True
            row.image_url = next_url
        if key_points is not None:
            cleaned = [p.strip() for p in key_points if str(p).strip()]
            row.key_points = cleaned[:12]
            content_changed = True
        if category is not None:
            raw = category.strip()
            if not raw:
                row.category = None
            else:
                cat = normalize_industry_category(raw)
                if not cat:
                    raise ValueError("invalid_category")
                row.category = cat

        if participation_suitable is not None:
            row.participation_suitable = bool(participation_suitable)
            if not row.participation_suitable:
                row.participation_type = None
                row.participation_question = None
                replace_participation_options(self.db, row, [])

        if show_sources is not None:
            row.show_sources = bool(show_sources)

        if push_title is not None:
            t = push_title.strip()
            row.push_title = t[:80] if t else None
        if push_body is not None:
            b = push_body.strip()
            row.push_body = b[:160] if b else None

        if participation_question is not None and row.participation_suitable:
            q = participation_question.strip()
            row.participation_question = q or None

        if participation_options is not None and row.participation_suitable:
            opts = [o.strip() for o in participation_options if str(o).strip()]
            if len(opts) < 2:
                raise ValueError("participation_needs_two_options")
            row.participation_type = row.participation_type or "binary"
            replace_participation_options(self.db, row, opts[:4])

        if content_changed:
            touch_content_updated(row)
        row.updated_at = datetime.utcnow()
        self.db.commit()
        return self.get(issue_id)

    async def upload_image(self, issue_id: str, file: UploadFile) -> IssueOut | None:
        row = self.db.query(Signal).filter(Signal.id == issue_id).first()
        if not row:
            return None
        if row.status == SignalStatus.REJECTED.value:
            raise ValueError("rejected_issue_cannot_edit")
        if row.status == SignalStatus.PUBLISHED.value:
            raise ValueError("published_issue_cannot_edit")

        path = await save_issue_image(file)
        delete_local_image_if_owned(getattr(row, "image_url", None))
        row.image_url = path
        touch_content_updated(row)
        row.updated_at = datetime.utcnow()
        self.db.commit()
        return self.get(issue_id)

    async def upload_column_media(self, issue_id: str, file: UploadFile) -> str | None:
        """Persist inline column image; does not mutate cover image_url."""
        row = self.db.query(Signal).filter(Signal.id == issue_id).first()
        if not row:
            return None
        if row.status == SignalStatus.REJECTED.value:
            raise ValueError("rejected_issue_cannot_edit")
        if row.status == SignalStatus.PUBLISHED.value:
            raise ValueError("published_issue_cannot_edit")
        return await save_issue_image(file)

    def publish(self, issue_id: str) -> IssueOut | None:
        row = self.db.query(Signal).filter(Signal.id == issue_id).first()
        if not row:
            return None
        if row.status == SignalStatus.PUBLISHED.value:
            return _to_issue_out(
            self.db, row, include_sources=True, expose_sources=True
        )
        if row.status == SignalStatus.REJECTED.value:
            raise ValueError("rejected_issue_cannot_publish")

        now = datetime.utcnow()
        row.status = SignalStatus.PUBLISHED.value
        row.lifecycle = "PUBLISHED"
        row.published_at = now
        row.updated_at = now
        if not getattr(row, "content_updated_at", None):
            touch_content_updated(row, now)
        self.db.commit()
        self.db.refresh(row)

        record_usage(ISSUE_PUBLISHED, 1, db=self.db)
        enqueue_signal_new(
            self.db,
            signal_id=row.id,
            title=row.title or "",
            related_symbols=row.related_symbols or [],
            evidence_level=row.evidence_level or "UNVERIFIED",
        )
        # Deliver immediately — don't wait for the next worker heavy cycle.
        try:
            from app.services.push_send_service import send_pending_pushes

            send_pending_pushes(self.db, limit=50)
        except Exception:
            logger.exception("admin publish push flush failed issue=%s", row.id)
        return _to_issue_out(
            self.db, row, include_sources=True, expose_sources=True
        )

    def reject(self, issue_id: str, *, reason: str | None = None) -> IssueOut | None:
        """Reject draft, or pull a published Issue off the consumer feed."""
        row = self.db.query(Signal).filter(Signal.id == issue_id).first()
        if not row:
            return None
        if row.status == SignalStatus.REJECTED.value:
            return _to_issue_out(
            self.db, row, include_sources=True, expose_sources=True
        )

        now = datetime.utcnow()
        row.status = SignalStatus.REJECTED.value
        row.lifecycle = "ARCHIVED"
        row.published_at = None
        row.updated_at = now
        _ = (reason or "").strip()
        self.db.commit()
        self.db.refresh(row)
        return _to_issue_out(
            self.db, row, include_sources=True, expose_sources=True
        )

    def unpublish(self, issue_id: str) -> IssueOut | None:
        """Published → draft (re-review without rejecting)."""
        row = self.db.query(Signal).filter(Signal.id == issue_id).first()
        if not row:
            return None
        if row.status != SignalStatus.PUBLISHED.value:
            raise ValueError("only_published_can_unpublish")

        now = datetime.utcnow()
        row.status = SignalStatus.DRAFT.value
        row.lifecycle = "CANDIDATE"
        row.published_at = None
        row.updated_at = now
        self.db.commit()
        self.db.refresh(row)
        return _to_issue_out(
            self.db, row, include_sources=True, expose_sources=True
        )

    def counts(self) -> dict[str, int]:
        def _n(status: str) -> int:
            return self.db.query(Signal).filter(Signal.status == status).count()

        return {
            "draft": _n("draft"),
            "published": _n("published"),
            "rejected": _n("rejected"),
        }
