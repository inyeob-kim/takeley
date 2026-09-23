"""TAKELEY columnist roster — operator-selected editorial bylines."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Columnist
from app.db.repositories.columnist_repository import ColumnistRepository
from app.schemas import (
    ColumnistIssueCardOut,
    ColumnistIssueListOut,
    ColumnistListOut,
    ColumnistOut,
    ColumnistProfileOut,
)
from app.services.issue_image_service import (
    delete_local_image_if_owned,
    normalize_image_url,
    save_issue_image,
)
from fastapi import UploadFile

_MAX_SPECIALTIES = 12
_MAX_SPECIALTY_LEN = 80
_MAX_EMAIL_LEN = 254
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_specialties(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = (item or "").strip()
        if not text:
            continue
        text = text[:_MAX_SPECIALTY_LEN]
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= _MAX_SPECIALTIES:
            break
    return out


class ColumnistError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def normalize_contact_email(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    text = text[:_MAX_EMAIL_LEN]
    if not _EMAIL_RE.match(text):
        raise ColumnistError("invalid_contact_email")
    return text


def public_email(row: Columnist) -> str | None:
    if not getattr(row, "show_email", False):
        return None
    return (getattr(row, "contact_email", None) or "").strip() or None


def profile_is_public(row: Columnist | None) -> bool:
    if row is None:
        return False
    return bool(getattr(row, "profile_public", True))


def _out(row: Columnist) -> ColumnistOut:
    return ColumnistOut(
        id=row.id,
        display_name=row.display_name,
        headline=row.headline or "",
        bio=row.bio or "",
        specialties=normalize_specialties(getattr(row, "specialties", None)),
        contact_email=getattr(row, "contact_email", None),
        show_email=bool(getattr(row, "show_email", False)),
        profile_public=profile_is_public(row),
        image_url=row.image_url,
        status=row.status,
        sort_order=int(row.sort_order or 0),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _sync_draft_snapshots(repo: ColumnistRepository, row: Columnist) -> None:
    """Keep unpublished bylines in sync; published Issues keep their snapshot."""
    for issue in repo.draft_issues_for(row.id):
        issue.column_author_name = row.display_name
        issue.column_author_image_url = row.image_url


class ColumnistService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ColumnistRepository(db)

    def list_admin(self, *, status: str | None = None, limit: int = 100) -> ColumnistListOut:
        if status and status not in ("active", "archived"):
            raise ColumnistError("invalid_status")
        rows = self.repo.list_all(status=status, limit=limit)
        items = [_out(r) for r in rows]
        return ColumnistListOut(items=items, count=len(items))

    def list_active_for_picker(self) -> ColumnistListOut:
        return self.list_admin(status="active", limit=200)

    def get_admin(self, columnist_id: str) -> ColumnistOut:
        row = self.repo.get(columnist_id)
        if not row:
            raise ColumnistError("Columnist not found", status_code=404)
        return _out(row)

    def create(
        self,
        *,
        display_name: str,
        headline: str = "",
        bio: str = "",
        specialties: list[str] | None = None,
        contact_email: str | None = None,
        show_email: bool = False,
        profile_public: bool = True,
        image_url: str | None = None,
        status: str = "active",
        sort_order: int | None = None,
    ) -> ColumnistOut:
        name = display_name.strip()
        if not name:
            raise ColumnistError("display_name_required")
        if status not in ("active", "archived"):
            raise ColumnistError("invalid_status")
        try:
            image = normalize_image_url(image_url)
        except ValueError as exc:
            raise ColumnistError(str(exc)) from exc
        order = sort_order if sort_order is not None else self.repo.next_sort_order()
        now = datetime.utcnow()
        row = Columnist(
            display_name=name[:128],
            headline=(headline or "").strip()[:160],
            bio=(bio or "").strip(),
            specialties=normalize_specialties(specialties),
            contact_email=normalize_contact_email(contact_email),
            show_email=bool(show_email),
            profile_public=bool(profile_public),
            image_url=image,
            status=status,
            sort_order=int(order),
            created_at=now,
            updated_at=now,
        )
        return _out(self.repo.add(row))

    def update(
        self,
        columnist_id: str,
        *,
        display_name: str | None = None,
        headline: str | None = None,
        bio: str | None = None,
        specialties: list[str] | None = None,
        contact_email: str | None = None,
        show_email: bool | None = None,
        profile_public: bool | None = None,
        image_url: str | None = None,
        clear_image: bool = False,
        status: str | None = None,
        sort_order: int | None = None,
    ) -> ColumnistOut:
        row = self.repo.get(columnist_id)
        if not row:
            raise ColumnistError("Columnist not found", status_code=404)
        if display_name is not None:
            name = display_name.strip()
            if not name:
                raise ColumnistError("display_name_required")
            row.display_name = name[:128]
        if headline is not None:
            row.headline = headline.strip()[:160]
        if bio is not None:
            row.bio = bio.strip()
        if specialties is not None:
            row.specialties = normalize_specialties(specialties)
        if contact_email is not None:
            row.contact_email = normalize_contact_email(contact_email)
        if show_email is not None:
            row.show_email = bool(show_email)
        if profile_public is not None:
            row.profile_public = bool(profile_public)
        if clear_image:
            delete_local_image_if_owned(row.image_url)
            row.image_url = None
        elif image_url is not None:
            try:
                next_url = normalize_image_url(image_url)
            except ValueError as exc:
                raise ColumnistError(str(exc)) from exc
            if next_url != (row.image_url or None):
                delete_local_image_if_owned(row.image_url)
            row.image_url = next_url
        if status is not None:
            if status not in ("active", "archived"):
                raise ColumnistError("invalid_status")
            row.status = status
        if sort_order is not None:
            row.sort_order = int(sort_order)
        row.updated_at = datetime.utcnow()
        saved = self.repo.save(row)
        _sync_draft_snapshots(self.repo, saved)
        self.db.commit()
        return _out(saved)

    async def upload_image(self, columnist_id: str, file: UploadFile) -> ColumnistOut:
        row = self.repo.get(columnist_id)
        if not row:
            raise ColumnistError("Columnist not found", status_code=404)
        try:
            url = await save_issue_image(file)
        except ValueError as exc:
            raise ColumnistError(str(exc)) from exc
        delete_local_image_if_owned(row.image_url)
        row.image_url = url
        row.updated_at = datetime.utcnow()
        saved = self.repo.save(row)
        _sync_draft_snapshots(self.repo, saved)
        self.db.commit()
        return _out(saved)

    def _issue_card(self, issue) -> ColumnistIssueCardOut:
        return ColumnistIssueCardOut(
            id=issue.id,
            title=issue.title,
            summary=issue.summary or "",
            category=issue.category,
            image_url=issue.image_url,
            published_at=issue.published_at or issue.first_seen_at,
            content_updated_at=getattr(issue, "content_updated_at", None),
        )

    def _page_bounds(self, *, limit: int | None, offset: int) -> tuple[int, int]:
        settings = get_settings()
        page = limit if limit is not None else settings.columnist_issue_page_size
        page = max(1, min(page, settings.columnist_issue_page_max))
        return page, max(0, offset)

    def _require_public_row(self, columnist_id: str) -> Columnist:
        row = self.repo.get(columnist_id)
        if not row or not profile_is_public(row):
            raise ColumnistError("Columnist not found", status_code=404)
        return row

    def public_profile(
        self, columnist_id: str, *, limit: int | None = None
    ) -> ColumnistProfileOut:
        row = self._require_public_row(columnist_id)
        page, _ = self._page_bounds(limit=limit, offset=0)
        total = self.repo.count_published_issues(columnist_id)
        issues = self.repo.published_issues(columnist_id, limit=page, offset=0)
        return ColumnistProfileOut(
            id=row.id,
            display_name=row.display_name,
            headline=row.headline or "",
            bio=row.bio or "",
            specialties=normalize_specialties(getattr(row, "specialties", None)),
            email=public_email(row),
            image_url=row.image_url,
            status=row.status,
            issue_count=total,
            issues=[self._issue_card(issue) for issue in issues],
        )

    def public_issues(
        self,
        columnist_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> ColumnistIssueListOut:
        row = self._require_public_row(columnist_id)
        page, skip = self._page_bounds(limit=limit, offset=offset)
        total = self.repo.count_published_issues(columnist_id)
        issues = self.repo.published_issues(columnist_id, limit=page, offset=skip)
        return ColumnistIssueListOut(
            items=[self._issue_card(issue) for issue in issues],
            count=total,
            offset=skip,
            limit=page,
        )

    def apply_to_issue(self, issue, columnist_id: str | None) -> None:
        """Stamp Issue FK + byline snapshot. Caller persists the Issue."""
        if not columnist_id:
            issue.columnist_id = None
            issue.column_author_name = None
            issue.column_author_image_url = None
            return
        row = self.repo.get(columnist_id)
        if not row:
            raise ColumnistError("Columnist not found", status_code=404)
        if row.status != "active":
            raise ColumnistError("columnist_not_active")
        issue.columnist_id = row.id
        issue.column_author_name = row.display_name
        issue.column_author_image_url = row.image_url
