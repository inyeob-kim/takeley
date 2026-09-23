"""Persistence for TAKELEY-selected columnists."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Columnist, Issue


class ColumnistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, columnist_id: str) -> Columnist | None:
        return (
            self.db.query(Columnist)
            .filter(Columnist.id == columnist_id)
            .one_or_none()
        )

    def list_all(self, *, status: str | None = None, limit: int = 100) -> list[Columnist]:
        q = self.db.query(Columnist)
        if status:
            q = q.filter(Columnist.status == status)
        return (
            q.order_by(Columnist.sort_order.asc(), Columnist.display_name.asc())
            .limit(limit)
            .all()
        )

    def next_sort_order(self) -> int:
        current = self.db.query(func.max(Columnist.sort_order)).scalar()
        return int(current or 0) + 1

    def add(self, row: Columnist) -> Columnist:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Columnist) -> Columnist:
        self.db.commit()
        self.db.refresh(row)
        return row

    def published_issues(
        self, columnist_id: str, *, limit: int = 40, offset: int = 0
    ) -> list[Issue]:
        return (
            self.db.query(Issue)
            .filter(
                Issue.columnist_id == columnist_id,
                Issue.status == "published",
            )
            .order_by(Issue.published_at.desc(), Issue.first_seen_at.desc())
            .offset(max(0, offset))
            .limit(limit)
            .all()
        )

    def count_published_issues(self, columnist_id: str) -> int:
        return (
            self.db.query(Issue)
            .filter(
                Issue.columnist_id == columnist_id,
                Issue.status == "published",
            )
            .count()
        )

    def draft_issues_for(self, columnist_id: str) -> list[Issue]:
        return (
            self.db.query(Issue)
            .filter(
                Issue.columnist_id == columnist_id,
                Issue.status == "draft",
            )
            .all()
        )
