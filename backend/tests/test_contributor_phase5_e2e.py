"""Phase 5 — Contributor E2E validation & hardening (P0/P1 gaps).

Does not add product features. Covers authorization matrix leftovers,
ownership, invalid transitions, activity gates, and the full happy path.
"""

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


def _issue(db: Session, *, title: str = "이슈 제목") -> Signal:
    row = Signal(
        title=title,
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


# --- Application matrix ---


@pytest.mark.parametrize(
    "status,code",
    [
        ("PENDING", 409),
        ("APPROVED", 409),
        ("SUSPENDED", 403),
    ],
)
def test_apply_blocked_by_status(status: str, code: int):
    db = _session()
    user = _user(db, status=status)
    with pytest.raises(ContributorError) as ei:
        ContributorService(db).apply(
            user.id, motivation="a", interests="b", sample_text="c"
        )
    assert ei.value.status_code == code


def test_rejected_reapply_then_approve_happy():
    db = _session()
    user = _user(db)
    svc = ContributorService(db)
    app = svc.apply(user.id, motivation="a", interests="b", sample_text="c")
    svc.reject_application(app.id, reason="보완")
    again = svc.apply(user.id, motivation="다시", interests="AI", sample_text="샘플")
    approved = svc.approve_application(again.id)
    assert approved.status == "APPROVED"
    db.refresh(user)
    assert user.contributor_status == "APPROVED"


# --- Ownership ---


def test_other_user_cannot_submit_or_withdraw():
    db = _session()
    author = _user(db, device="author")
    other = _user(db, device="other")
    _approve(db, author)
    _approve(db, other)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=author.id, title="t", body="b")
    with pytest.raises(ContributorError) as ei:
        svc.submit(issue.id, take.id, user_id=other.id)
    assert ei.value.status_code == 403
    take = svc.submit(issue.id, take.id, user_id=author.id)
    with pytest.raises(ContributorError) as ei2:
        svc.withdraw(issue.id, take.id, user_id=other.id)
    assert ei2.value.status_code == 403


def test_take_wrong_issue_path_is_404():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue_a = _issue(db, title="A")
    issue_b = _issue(db, title="B")
    svc = TakeService(db)
    take = svc.create(issue_a.id, user_id=user.id, title="t", body="b")
    with pytest.raises(ContributorError) as ei:
        svc.update(issue_b.id, take.id, user_id=user.id, title="hack")
    assert ei.value.status_code == 404


# --- Invalid transitions ---


def test_invalid_state_transitions_rejected():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    svc = TakeService(db)
    draft = svc.create(issue.id, user_id=user.id, title="t", body="b")

    with pytest.raises(ContributorError):
        svc.admin_publish(draft.id)
    with pytest.raises(ContributorError):
        svc.admin_reject(draft.id)
    with pytest.raises(ContributorError):
        svc.admin_unpublish(draft.id)

    pending = svc.submit(issue.id, draft.id, user_id=user.id)
    with pytest.raises(ContributorError):
        svc.submit(issue.id, pending.id, user_id=user.id)
    with pytest.raises(ContributorError):
        svc.update(issue.id, pending.id, user_id=user.id, title="no")

    published = svc.admin_publish(pending.id)
    with pytest.raises(ContributorError):
        svc.admin_publish(published.id)
    with pytest.raises(ContributorError):
        svc.submit(issue.id, published.id, user_id=user.id)

    rejected = svc.admin_unpublish(published.id, reason="회수")
    assert rejected.status == "rejected"
    with pytest.raises(ContributorError):
        svc.admin_publish(rejected.id)


# --- Activity gates ---


@pytest.mark.parametrize("status", ["NONE", "PENDING", "REJECTED", "SUSPENDED"])
def test_activity_hidden_unless_approved(status: str):
    db = _session()
    user = _user(db, status=status)
    act = IssueService(db).my_activity(user.id)
    assert act.contributor_stats is None
    assert act.my_deep_thoughts == []


def test_approved_activity_aggregates_views_and_reactions():
    db = _session()
    author = _user(db, device="a")
    reader = _user(db, device="r")
    _approve(db, author)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=author.id, title="깊은", body="본문")
    take = svc.submit(issue.id, take.id, user_id=author.id)
    take = svc.admin_publish(take.id)
    svc.get_for_reader(issue.id, take.id, user_id=reader.id, record_view=True)
    svc.add_reaction(issue.id, take.id, user_id=reader.id)
    act = IssueService(db).my_activity(author.id)
    assert act.contributor_stats is not None
    assert act.contributor_stats.takes_count == 1
    assert act.contributor_stats.total_views >= 1
    assert act.contributor_stats.total_reactions == 1


# --- SUSPENDED vs ordinary user ---


def test_suspended_blocks_writing_but_can_participate_and_react():
    db = _session()
    author = _user(db, device="author")
    suspended = _user(db, device="sus")
    _approve(db, author)
    _approve(db, suspended)
    issue = _issue(db)
    issue.participation_suitable = True
    issue.participation_question = "어떻게 보세요?"
    replace_participation_options(db, issue, ["찬성", "반대"])
    db.commit()
    db.refresh(issue)

    svc = TakeService(db)
    take = svc.create(issue.id, user_id=author.id, title="t", body="b")
    take = svc.submit(issue.id, take.id, user_id=author.id)
    take = svc.admin_publish(take.id)

    suspended.contributor_status = "SUSPENDED"
    db.commit()

    with pytest.raises(ContributorError):
        svc.create(issue.id, user_id=suspended.id, title="x", body="y")

    # Ordinary participation still works
    opt = issue.participation_options[0]
    voted = IssueService(db).participate(
        issue.id, user_id=suspended.id, option_id=opt.id
    )
    assert voted is not None
    assert voted["my_option_id"] == opt.id

    # Reaction as ordinary user still works
    r = svc.add_reaction(issue.id, take.id, user_id=suspended.id)
    assert r.reaction_count == 1


def test_suspended_cannot_edit_or_submit_existing_draft():
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=user.id, title="t", body="b")
    user.contributor_status = "SUSPENDED"
    db.commit()
    with pytest.raises(ContributorError):
        svc.update(issue.id, take.id, user_id=user.id, title="x")
    with pytest.raises(ContributorError):
        svc.submit(issue.id, take.id, user_id=user.id)


# --- Reactions multi-user ---


def test_second_user_reaction_is_independent():
    db = _session()
    author = _user(db, device="a")
    r1 = _user(db, device="r1")
    r2 = _user(db, device="r2")
    _approve(db, author)
    issue = _issue(db)
    svc = TakeService(db)
    take = svc.create(issue.id, user_id=author.id, title="t", body="b")
    take = svc.submit(issue.id, take.id, user_id=author.id)
    take = svc.admin_publish(take.id)
    assert svc.add_reaction(issue.id, take.id, user_id=r1.id).reaction_count == 1
    assert svc.add_reaction(issue.id, take.id, user_id=r1.id).already_reacted is True
    assert svc.add_reaction(issue.id, take.id, user_id=r2.id).reaction_count == 2


# --- Full happy-path smoke ---


def test_full_contributor_happy_path_smoke():
    db = _session()
    applicant = _user(db, device="writer")
    reader = _user(db, device="reader")
    svc_c = ContributorService(db)
    svc_t = TakeService(db)

    app = svc_c.apply(
        applicant.id,
        motivation="생각을 나누고 싶어요",
        interests="경제",
        sample_text="샘플",
    )
    assert app.status == "PENDING"
    assert (
        db.query(IssueUserEvent)
        .filter(IssueUserEvent.event == "contributor_apply")
        .count()
        == 1
    )

    approved = svc_c.approve_application(app.id)
    assert approved.status == "APPROVED"
    db.refresh(applicant)
    assert applicant.contributor_status == "APPROVED"

    issue = _issue(db)
    take = svc_t.create(
        issue.id,
        user_id=applicant.id,
        title="깊이 있는 제목",
        body="깊이 있는 본문",
        source_urls=["https://example.com"],
    )
    assert take.issue_id == issue.id
    assert take.status == "draft"

    take = svc_t.update(
        issue.id,
        take.id,
        user_id=applicant.id,
        body="수정된 본문",
    )
    assert take.status == "draft"

    take = svc_t.submit(issue.id, take.id, user_id=applicant.id)
    assert take.status == "pending_review"

    published = svc_t.admin_publish(take.id)
    assert published.status == "published"
    assert svc_t.list_published(issue.id).count == 1

    viewed = svc_t.get_for_reader(
        issue.id, take.id, user_id=reader.id, record_view=True
    )
    assert viewed.view_count == 1
    reacted = svc_t.add_reaction(issue.id, take.id, user_id=reader.id)
    assert reacted.reaction_count == 1

    act = IssueService(db).my_activity(applicant.id)
    assert act.contributor_stats is not None
    assert act.contributor_stats.takes_count == 1
    assert act.contributor_stats.total_views == 1
    assert act.contributor_stats.total_reactions == 1
    assert len(act.my_deep_thoughts) == 1
    assert act.my_deep_thoughts[0].status == "published"

    # Unpublish removes from public list
    svc_t.admin_unpublish(take.id, reason="회수")
    assert svc_t.list_published(issue.id).count == 0


# --- Admin HTTP auth matrix ---


def test_admin_endpoints_require_valid_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "phase5-admin-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    client = TestClient(app)
    paths = [
        "/api/v1/admin/contributor/applications",
        "/api/v1/admin/contributor/takes",
    ]
    for path in paths:
        assert client.get(path).status_code == 401
        assert (
            client.get(path, headers={"X-Admin-Key": "wrong"}).status_code == 401
        )
        assert (
            client.get(
                path, headers={"X-Admin-Key": "phase5-admin-key"}
            ).status_code
            == 200
        )
    get_settings.cache_clear()


def test_http_issue_id_mismatch_on_create(monkeypatch):
    """Path issue_id is authoritative; body.issue_id mismatch → 400."""
    db = _session()
    user = _user(db)
    _approve(db, user)
    issue = _issue(db)

    engine, SessionLocal = _engine_session()
    # Rebuild with same data is hard — use dependency override on fresh app DB.
    # Instead drive TakeService via HTTP with shared session override.

    from app.core.config import get_settings
    from app.main import app

    get_settings.cache_clear()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    r = client.post(
        f"/api/v1/issues/{issue.id}/takes?user_id={user.id}",
        json={
            "title": "제목",
            "body": "본문입니다",
            "source_urls": [],
            "issue_id": "not-the-path-id",
            "user_id": user.id,
        },
    )
    assert r.status_code == 400
    app.dependency_overrides.clear()
    get_settings.cache_clear()
