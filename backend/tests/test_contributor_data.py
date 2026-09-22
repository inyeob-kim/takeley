"""Phase 1 Contributor data-layer model / schema checks (no API)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    ContributorApplication,
    IssueTake,
    IssueTakeReaction,
    IssueUserEvent,
    Signal,
    User,
)
from app.db.session import Base


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db: Session, device_id: str = "dev-1") -> User:
    user = User(device_id=device_id, platform="web")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _issue(db: Session) -> Signal:
    issue = Signal(
        title="테스트 이슈",
        summary="요약",
        status="published",
        published_at=datetime.utcnow(),
        first_seen_at=datetime.utcnow(),
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


def test_user_contributor_status_defaults_to_none():
    db = _session()
    user = _user(db)
    assert user.contributor_status == "NONE"
    assert user.display_name is None
    assert user.contributor_approved_at is None
    # Orthogonal to account status / plan.
    assert user.status == "active"
    assert user.plan_type == "FREE"


def test_issue_take_defaults_and_required_fks():
    db = _session()
    user = _user(db)
    issue = _issue(db)
    take = IssueTake(
        issue_id=issue.id,
        author_id=user.id,
        title="깊이 있는 제목",
        body="본문",
    )
    db.add(take)
    db.commit()
    db.refresh(take)
    assert take.status == "draft"
    assert take.view_count == 0
    assert take.reaction_count == 0
    assert take.published_at is None
    assert take.featured_at is None
    assert take.issue_id == issue.id
    assert take.author_id == user.id


def test_issue_take_requires_issue_and_author():
    db = _session()
    take = IssueTake(title="x", body="y")
    db.add(take)
    with pytest.raises(IntegrityError):
        db.commit()


def test_reaction_unique_per_user_take():
    db = _session()
    user = _user(db)
    issue = _issue(db)
    take = IssueTake(
        issue_id=issue.id,
        author_id=user.id,
        title="t",
        body="b",
    )
    db.add(take)
    db.commit()
    db.refresh(take)

    db.add(IssueTakeReaction(take_id=take.id, user_id=user.id))
    db.commit()
    db.add(IssueTakeReaction(take_id=take.id, user_id=user.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_issue_user_event_take_id_nullable():
    db = _session()
    issue = _issue(db)
    ev = IssueUserEvent(
        user_id="u1",
        signal_id=issue.id,
        event="open",
        take_id=None,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    assert ev.take_id is None

    user = _user(db, device_id="dev-2")
    take = IssueTake(
        issue_id=issue.id,
        author_id=user.id,
        title="t",
        body="b",
    )
    db.add(take)
    db.commit()
    db.refresh(take)
    ev2 = IssueUserEvent(
        user_id=user.id,
        signal_id=issue.id,
        event="take_view",
        take_id=take.id,
    )
    db.add(ev2)
    db.commit()
    db.refresh(ev2)
    assert ev2.take_id == take.id


def test_contributor_application_defaults():
    db = _session()
    user = _user(db)
    app = ContributorApplication(
        user_id=user.id,
        motivation="이유",
        interests="Tech",
        sample_text="샘플",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    assert app.status == "PENDING"


def test_planned_event_names_fit_string32():
    names = [
        "contributor_apply",
        "contributor_approved",
        "take_submit",
        "take_published",
        "take_view",
        "take_open",
        "take_react",
    ]
    for name in names:
        assert len(name) <= 32, name


def test_schema_has_contributor_tables():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    tables = set(inspect(engine).get_table_names())
    assert "contributor_applications" in tables
    assert "issue_takes" in tables
    assert "issue_take_reactions" in tables
    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    assert "display_name" in cols
    assert "contributor_status" in cols
    assert "contributor_approved_at" in cols
    event_cols = {c["name"] for c in inspect(engine).get_columns("issue_user_events")}
    assert "take_id" in event_cols
