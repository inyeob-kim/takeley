"""Public site reads. Issues stay on the issues table; no new content types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Columnist, Issue, IssueTake, User
from app.pipeline.industries import INDUSTRY_LABELS
from app.schemas import IssueOut
from app.services.issue_service import IssueService

_CATEGORY_ORDER = list(INDUSTRY_LABELS.values())


@dataclass
class ColumnCard:
    id: str
    title: str
    summary: str
    category: str | None
    image_url: str | None
    author: str | None
    headline: str | None
    published_at: datetime | None
    column_body: str


@dataclass
class TakeCard:
    id: str
    issue_id: str
    issue_title: str
    title: str
    body: str
    author: str | None
    published_at: datetime | None


class SiteService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def issues(
        self,
        *,
        limit: int = 24,
        sort: str = "trending",
        category: str | None = None,
        q: str | None = None,
    ) -> list[IssueOut]:
        # No user id: the site must not attach the demo user's vote.
        return IssueService(self.db).list_issues(
            limit=limit,
            sort=sort,
            category=category,
            q=q,
            user_id=None,
        ).items

    def issue(self, issue_id: str) -> IssueOut | None:
        return IssueService(self.db).get_issue(issue_id, user_id=None)

    def categories_in_use(self) -> list[str]:
        rows = (
            self.db.query(Issue.category)
            .filter(Issue.status == "published", Issue.category.isnot(None))
            .distinct()
            .all()
        )
        found = {(row[0] or "").strip() for row in rows if (row[0] or "").strip()}
        ordered = [label for label in _CATEGORY_ORDER if label in found]
        extra = sorted(found - set(ordered))
        return ordered + extra

    def columns(self, *, limit: int = 24) -> list[ColumnCard]:
        # NEWS also stores body in column_body — keep it off the editorial 칼럼 list.
        rows = (
            self.db.query(Issue, Columnist)
            .outerjoin(Columnist, Columnist.id == Issue.columnist_id)
            .filter(Issue.status == "published")
            .filter(Issue.content_kind == "ISSUE")
            .filter(func.length(func.trim(Issue.column_body)) > 80)
            .order_by(Issue.published_at.desc())
            .limit(max(1, min(limit, 40)))
            .all()
        )
        cards: list[ColumnCard] = []
        for issue, columnist in rows:
            headline = None
            if (
                columnist
                and columnist.status == "active"
                and (columnist.headline or "").strip()
            ):
                headline = columnist.headline.strip()
            author = (issue.column_author_name or "").strip() or None
            cards.append(
                ColumnCard(
                    id=issue.id,
                    title=issue.title,
                    summary=issue.summary or "",
                    category=(issue.category or "").strip() or None,
                    image_url=(issue.image_url or "").strip() or None,
                    author=author,
                    headline=headline,
                    published_at=issue.published_at,
                    column_body=issue.column_body or "",
                )
            )
        return cards

    def takes(self, *, limit: int = 8) -> list[TakeCard]:
        rows = (
            self.db.query(IssueTake, Issue, User)
            .join(Issue, Issue.id == IssueTake.issue_id)
            .outerjoin(User, User.id == IssueTake.author_id)
            .filter(IssueTake.status == "published", Issue.status == "published")
            .order_by(IssueTake.published_at.desc(), IssueTake.created_at.desc())
            .limit(max(1, min(limit, 20)))
            .all()
        )
        return [_take_card(take, issue, user) for take, issue, user in rows]

    def take(self, take_id: str) -> TakeCard | None:
        row = (
            self.db.query(IssueTake, Issue, User)
            .join(Issue, Issue.id == IssueTake.issue_id)
            .outerjoin(User, User.id == IssueTake.author_id)
            .filter(
                IssueTake.id == take_id,
                IssueTake.status == "published",
                Issue.status == "published",
            )
            .first()
        )
        if not row:
            return None
        return _take_card(row[0], row[1], row[2])

    def related(self, issue_id: str, category: str | None, *, limit: int = 3) -> list[Issue]:
        # Share landing "다른 이슈" is Issue discovery — never surface NEWS cards.
        query = self.db.query(Issue).filter(
            Issue.status == "published",
            Issue.content_kind == "ISSUE",
            Issue.id != issue_id,
        )
        label = (category or "").strip()
        if label:
            query = query.filter(Issue.category == label)
        return (
            query.order_by(Issue.published_at.desc()).limit(max(1, min(limit, 6))).all()
        )


def _take_card(take: IssueTake, issue: Issue, user: User | None) -> TakeCard:
    author = (user.display_name or "").strip() if user else ""
    return TakeCard(
        id=take.id,
        issue_id=issue.id,
        issue_title=issue.title,
        title=take.title,
        body=take.body or "",
        author=author or None,
        published_at=take.published_at or take.created_at,
    )
