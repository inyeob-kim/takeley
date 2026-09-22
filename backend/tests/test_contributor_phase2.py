"""Phase 2 Contributor / IssueTake backend API tests."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import IssueUserEvent, Signal, User
from app.db.session import Base, get_db
from app.services.contributor_service import ContributorError, ContributorService
from app.services.issue_service import IssueService, replace_participation_options
from app.services.take_service import TakeService


def _engine_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)


def _session() -> Session:
    _, SessionLocal = _engine_session()
    return SessionLocal()


def _user(db: Session, *, device: str = "d1", status: str = "NONE") -> User:
    u = User(device_id=device, platform="web", contributor_status=status)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _issue(db: Session) -> Signal:
    row = Signal(
        title="이슈 제목",
        summary="요약",
        status="published",
        published_at=datetime.utcnow(),
        first_seen_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _approve(db: Session, user: User) -> None:
    svc = ContributorService(db)
    app = svc.apply(
        user.id,
        motivation="동기",
        interests="Tech",
        sample_text="샘플 본문입니다.",
    )
    svc.approve_application(app.id)
    db.refresh(user)


# --- Application ---


def test_apply_sets_pending_and_records_event():
    db = _session()
    user = _user(db)
    out = ContributorService(db).apply(
        user.id,
        motivation="왜",
        interests="AI",
        sample_text="예시",
    )
    assert out.status == "PENDING"
    db.refresh(user)
    assert user.contributor_status == "PENDING"
    ev = (
        db.query(IssueUserEvent)
        .filter(IssueUserEvent.event == "contributor_apply")
        .first()
    )
    assert ev is not None
    assert ev.user_id == user.id
    assert ev.signal_id is None


def test_duplicate_pending_application_rejected():
    db = _session()
    user = _user(db)
    svc = ContributorService(db)
    svc.apply(user.id, motivation="a", interests="b", sample_text="c")
    with pytest.raises(ContributorError) as ei:
        svc.apply(user.id, motivation="a2", interests="b2", sample_text="c2")
    assert ei.value.status_code == 409


def test_admin_approve_and_reject():
    db = _session()
    user = _user(db)
    svc = ContributorService(db)
    app = svc.apply(user.id, motivation="a", interests="b", sample_text="c")
    approved = svc.approve_application(app.id)
    assert approved.status == "APPROVED"
    db.refresh(user)
    assert user.contributor_status == "APPROVED"
    assert user.contributor_approved_at is not None
    assert (
        db.query(IssueUserEvent)
        .filter(IssueUserEvent.event == "contributor_approved")
        .count()
        == 1
    )

    user2 = _user(db, device="d2")
    app2 = svc.apply(user2.id, motivation="a", interests="b", sample_text="c")
    rejected = svc.reject_application(app2.id, reason="품질")
    assert rejected.status == "REJECTED"
    assert rejected.admin_note == "품질"
    db.refresh(user2)
    assert user2.contributor_status == "REJECTED"


def test_rejected_can_reapply():
    db = _session()
    user = _user(db)
    svc = ContributorService(db)
    app = svc.apply(user.id, motivation="a", interests="b", sample_text="c")
    svc.reject_application(app.id)
    again = svc.apply(user.id, motivation="다시", interests="Tech", sample_text="샘플")
    assert again.status == "PENDING"
    db.refresh(user)
    assert user.contributor_status == "PENDING"


# --- Permissions ---


@pytest.mark.parametrize("status", ["NONE", "PENDING", "REJECTED", "SUSPENDED"])
def test_non_approved_cannot_create_take(status: str):
    db = _session()
    user = _user(db, status=status)
    issue = _issue(db)
    with pytest.raises(ContributorError) as ei:
        TakeService(db).create(
            issue.id,
            user_id=user.id,
            title="제목",
            body="본문",
        )
    assert ei.value.status_code == 403


def test_inactive_user_cannot_create_take():
    db = _session()
    user = _user(db, status="APPROVED")
    user.status = "withdrawn"
    db.commit()
    issue = _issue(db)
    with pytest.raises(ContributorError) as ei:
        TakeService(db).create(
            issue.id, user_id=user.id, title="t", body="b"
        )
    assert ei.value.status_code == 403


def test_approved_can_create_draft():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    take = TakeService(db).create(
        issue.id, user_id=user.id, title="제목", body="본문"
    )
    assert take.status == "draft"
    assert take.author_id == user.id
    assert take.issue_id == issue.id
    assert take.view_count == 0
    assert take.reaction_count == 0


def test_issue_id_mismatch_rejected():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    with pytest.raises(ContributorError) as ei:
        TakeService(db).create(
            issue.id,
            user_id=user.id,
            title="t",
            body="b",
            body_issue_id="other-id",
        )
    assert ei.value.status_code == 400


# --- Lifecycle ---


def test_take_lifecycle_submit_withdraw_publish_reject():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=user.id, title="제목", body="본문입니다")
    take = svc.submit(issue.id, take.id, user_id=user.id)
    assert take.status == "pending_review"
    assert (
        db.query(IssueUserEvent)
        .filter(IssueUserEvent.event == "take_submit", IssueUserEvent.take_id == take.id)
        .count()
        == 1
    )
    take = svc.withdraw(issue.id, take.id, user_id=user.id)
    assert take.status == "draft"
    take = svc.submit(issue.id, take.id, user_id=user.id)
    published = svc.admin_publish(take.id)
    assert published.status == "published"
    assert published.published_at is not None
    assert (
        db.query(IssueUserEvent)
        .filter(
            IssueUserEvent.event == "take_published",
            IssueUserEvent.take_id == take.id,
        )
        .count()
        == 1
    )


def test_pending_and_published_not_editable():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=user.id, title="t", body="b")
    take = svc.submit(issue.id, take.id, user_id=user.id)
    with pytest.raises(ContributorError):
        svc.update(issue.id, take.id, user_id=user.id, title="x")
    take = svc.admin_publish(take.id)
    with pytest.raises(ContributorError):
        svc.update(issue.id, take.id, user_id=user.id, title="y")


def test_rejected_becomes_draft_on_edit():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=user.id, title="t", body="b")
    take = svc.submit(issue.id, take.id, user_id=user.id)
    svc.admin_reject(take.id, reason="보완 필요")
    updated = svc.update(issue.id, take.id, user_id=user.id, body="수정 본문")
    assert updated.status == "draft"
    assert updated.admin_note == "보완 필요"


def test_other_user_cannot_edit():
    db = _session()
    author = _user(db, device="a")
    other = _user(db, device="b", status="APPROVED")
    _approve(db, author)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=author.id, title="t", body="b")
    with pytest.raises(ContributorError) as ei:
        svc.update(issue.id, take.id, user_id=other.id, title="hack")
    assert ei.value.status_code == 403


# --- Visibility ---


def test_public_lists_published_only():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    svc = TakeService(db)
    draft = svc.create(issue.id, user_id=user.id, title="draft", body="b")
    pending = svc.create(issue.id, user_id=user.id, title="pend", body="b")
    pending = svc.submit(issue.id, pending.id, user_id=user.id)
    pub = svc.create(issue.id, user_id=user.id, title="pub", body="b")
    pub = svc.submit(issue.id, pub.id, user_id=user.id)
    pub = svc.admin_publish(pub.id)
    listed = svc.list_published(issue.id)
    assert listed.count == 1
    assert listed.items[0].id == pub.id
    with pytest.raises(ContributorError):
        svc.get_for_reader(issue.id, draft.id, user_id="stranger", record_view=False)
    with pytest.raises(ContributorError):
        svc.get_for_reader(issue.id, pending.id, user_id="stranger", record_view=False)
    own = svc.get_for_reader(issue.id, draft.id, user_id=user.id, record_view=False)
    assert own.status == "draft"


def test_suspended_cannot_submit_but_published_remains():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=user.id, title="t", body="b")
    take = svc.submit(issue.id, take.id, user_id=user.id)
    take = svc.admin_publish(take.id)
    user.contributor_status = "SUSPENDED"
    db.commit()
    with pytest.raises(ContributorError):
        svc.create(issue.id, user_id=user.id, title="new", body="b")
    listed = svc.list_published(issue.id)
    assert listed.count == 1


def test_admin_suspend_and_reinstate_contributor():
    db = _session()
    user = _user(db)
    c_svc = ContributorService(db)
    app = c_svc.apply(
        user.id,
        motivation="동기",
        interests="AI",
        sample_text="샘플 본문입니다.",
    )
    approved = c_svc.approve_application(app.id)
    assert approved.contributor_status == "APPROVED"

    suspended = c_svc.suspend_contributor(app.id, reason="정책 위반")
    assert suspended.contributor_status == "SUSPENDED"
    assert suspended.admin_note == "정책 위반"
    db.refresh(user)
    assert user.contributor_status == "SUSPENDED"

    again = c_svc.suspend_contributor(app.id)
    assert again.contributor_status == "SUSPENDED"

    reinstated = c_svc.reinstate_contributor(app.id)
    assert reinstated.contributor_status == "APPROVED"
    db.refresh(user)
    assert user.contributor_status == "APPROVED"


# --- Reactions / views ---


def test_reaction_unique_and_count():
    db = _session()
    author = _user(db, device="auth")
    reader = _user(db, device="reader")
    _approve(db, author)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=author.id, title="t", body="b")
    take = svc.submit(issue.id, take.id, user_id=author.id)
    take = svc.admin_publish(take.id)
    r1 = svc.add_reaction(issue.id, take.id, user_id=reader.id)
    assert r1.reaction_count == 1
    assert r1.already_reacted is False
    r2 = svc.add_reaction(issue.id, take.id, user_id=reader.id)
    assert r2.already_reacted is True
    assert r2.reaction_count == 1
    assert (
        db.query(IssueUserEvent)
        .filter(IssueUserEvent.event == "take_react", IssueUserEvent.take_id == take.id)
        .count()
        == 1
    )


def test_reaction_on_draft_forbidden():
    db = _session()
    author = _user(db, device="a")
    reader = _user(db, device="r")
    _approve(db, author)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=author.id, title="t", body="b")
    with pytest.raises(ContributorError):
        svc.add_reaction(issue.id, take.id, user_id=reader.id)


def test_detail_increments_view_and_records_take_open():
    db = _session()
    author = _user(db)
    _approve(db, author)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=author.id, title="t", body="b")
    take = svc.submit(issue.id, take.id, user_id=author.id)
    take = svc.admin_publish(take.id)
    out = svc.get_for_reader(issue.id, take.id, user_id="viewer-1", record_view=True)
    assert out.view_count == 1
    ev = (
        db.query(IssueUserEvent)
        .filter(IssueUserEvent.event == "take_open", IssueUserEvent.take_id == take.id)
        .first()
    )
    assert ev is not None
    assert ev.signal_id == issue.id


# --- Activity additive ---


def test_activity_additive_fields():
    db = _session()
    user = _user(db)
    # Non-approved
    act = IssueService(db).my_activity(user.id)
    assert act.contributor_stats is None
    assert act.my_deep_thoughts == []
    assert isinstance(act.participations, list)
    assert isinstance(act.followed, list)
    assert isinstance(act.comments, list)

    _approve(db, user)
    issue = _issue(db)
    replace_participation_options(db, issue, ["찬성", "반대"])
    db.commit()
    TakeService(db).create(issue.id, user_id=user.id, title="깊은 생각", body="본문")
    act2 = IssueService(db).my_activity(user.id)
    assert act2.contributor_stats is not None
    assert act2.contributor_stats.takes_count == 1
    assert len(act2.my_deep_thoughts) == 1
    assert act2.my_deep_thoughts[0].title == "깊은 생각"
    assert act2.my_deep_thoughts[0].issue_title == "이슈 제목"


# --- Admin HTTP auth ---


def test_admin_contributor_requires_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret-test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/v1/admin/contributor/applications")
    assert r.status_code == 401
    r2 = client.get(
        "/api/v1/admin/contributor/applications",
        headers={"X-Admin-Key": "secret-test-key"},
    )
    assert r2.status_code == 200
    get_settings.cache_clear()


def test_admin_unpublish_to_rejected():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=user.id, title="t", body="b")
    take = svc.submit(issue.id, take.id, user_id=user.id)
    take = svc.admin_publish(take.id)
    out = svc.admin_unpublish(take.id, reason="회수")
    assert out.status == "rejected"
    assert svc.list_published(issue.id).count == 0
