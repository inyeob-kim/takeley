"""Admin Issue review API tests (in-memory SQLite)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_admin_requires_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret-test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/v1/admin/issues/counts")
    assert r.status_code == 401

    r2 = client.get(
        "/api/v1/admin/issues/counts",
        headers={"X-Admin-Key": "secret-test-key"},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert "draft" in body
    get_settings.cache_clear()


def test_admin_disabled_without_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    client = TestClient(app)
    r = client.get(
        "/api/v1/admin/issues/counts",
        headers={"X-Admin-Key": "anything"},
    )
    assert r.status_code == 503
    get_settings.cache_clear()


def test_published_issue_edit_bumps_content_updated():
    from datetime import datetime, timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Signal
    from app.db.session import Base
    from app.services.admin_issue_service import AdminIssueService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    stamped = datetime.utcnow() - timedelta(hours=2)
    row = Signal(
        title="배포된 이슈 제목입니다",
        summary="배포된 이슈 요약입니다.",
        status="published",
        lifecycle="PUBLISHED",
        published_at=stamped,
        first_seen_at=stamped,
        content_updated_at=stamped,
        column_body="원래 칼럼",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    svc = AdminIssueService(db)
    out = svc.update(row.id, title="고친 이슈 제목입니다", column_body="고친 칼럼")
    assert out is not None
    db.refresh(row)
    assert row.column_body == "고친 칼럼"
    assert row.title == "고친 이슈 제목입니다"
    assert row.content_updated_at is not None
    assert row.content_updated_at > stamped
    assert row.lifecycle == "UPDATED"


def test_rejected_issue_cannot_be_edited():
    from datetime import datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Signal
    from app.db.session import Base
    from app.services.admin_issue_service import AdminIssueService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    row = Signal(
        title="폐기된 이슈 제목입니다",
        summary="폐기된 이슈 요약입니다.",
        status="rejected",
        first_seen_at=datetime.utcnow(),
        column_body="원래 칼럼",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    svc = AdminIssueService(db)
    try:
        svc.update(row.id, title="바꾸면 안 됨 제목입니다", column_body="해킹")
        raised = False
    except ValueError as exc:
        raised = True
        assert "rejected_issue_cannot_edit" in str(exc)
    assert raised
    db.refresh(row)
    assert row.column_body == "원래 칼럼"


def test_create_manual_column_draft():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.session import Base
    from app.services.admin_issue_service import AdminIssueService
    from app.services.columnist_service import ColumnistService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    columnist = ColumnistService(db).create(
        display_name="김칼럼",
        headline="테이클리 선정",
    )
    svc = AdminIssueService(db)
    out = svc.create_manual(columnist_id=columnist.id)
    assert out.status == "draft"
    assert out.title == "새 칼럼 초안"
    assert out.columnist_id == columnist.id
    assert out.column_author_name == "김칼럼"
    assert out.source_count == 0
    assert out.participation_suitable is False


def test_published_issue_save_keeps_votes_when_renaming_options():
    from datetime import datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Participation, ParticipationOption, Signal
    from app.db.session import Base
    from app.services.admin_issue_service import AdminIssueService
    from app.services.issue_service import replace_participation_options

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    row = Signal(
        title="배포된 이슈 제목입니다",
        summary="배포된 이슈 요약입니다.",
        status="published",
        lifecycle="PUBLISHED",
        published_at=datetime.utcnow(),
        first_seen_at=datetime.utcnow(),
        participation_suitable=True,
        participation_question="어떻게 생각해?",
        participation_type="binary",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    replace_participation_options(db, row, ["된다", "안 된다"])
    db.commit()
    db.refresh(row)
    opt0 = sorted(row.participation_options, key=lambda o: o.display_order)[0]
    opt0_id = opt0.id
    db.add(
        Participation(
            signal_id=row.id,
            user_id="u-vote-1",
            option_id=opt0_id,
        )
    )
    db.commit()

    svc = AdminIssueService(db)
    out = svc.update(
        row.id,
        title="배포된 이슈 제목입니다",
        summary="배포된 이슈 요약입니다.",
        why_it_matters="",
        column_body="",
        participation_suitable=True,
        participation_question="어떻게 생각해?",
        participation_options=["더 간다", "꺾인다"],
    )
    assert out is not None
    db.refresh(row)
    opts = sorted(row.participation_options, key=lambda o: o.display_order)
    assert [o.label for o in opts[:2]] == ["더 간다", "꺾인다"]
    assert opts[0].id == opt0_id
    vote = (
        db.query(Participation)
        .filter(Participation.user_id == "u-vote-1", Participation.signal_id == row.id)
        .one()
    )
    assert vote.option_id == opt0_id


def test_schedule_publish_due_and_clear():
    from datetime import datetime, timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Signal
    from app.db.session import Base
    from app.services.admin_issue_service import AdminIssueService
    from app.services.issue_service import IssueService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    row = Signal(
        title="예약 배포 이슈 제목입니다",
        summary="예약 배포 이슈 요약입니다.",
        status="draft",
        lifecycle="CANDIDATE",
        topic="column",
        first_seen_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    svc = AdminIssueService(db)
    future = datetime.utcnow() + timedelta(hours=2)
    scheduled = svc.schedule(row.id, future)
    assert scheduled is not None
    assert scheduled.status == "draft"
    assert scheduled.scheduled_publish_at is not None
    db.refresh(row)
    assert row.status == "draft"
    assert row.scheduled_publish_at is not None

    # Still invisible on consumer feed.
    feed = IssueService(db).list_issues(limit=20)
    assert all(i.id != row.id for i in feed.items)

    # Not due yet.
    assert svc.publish_due(now=datetime.utcnow()) == 0
    db.refresh(row)
    assert row.status == "draft"

    # Due → publish + clear schedule.
    published_n = svc.publish_due(now=future + timedelta(seconds=1))
    assert published_n == 1
    db.refresh(row)
    assert row.status == "published"
    assert row.published_at is not None
    assert row.scheduled_publish_at is None

    feed2 = IssueService(db).list_issues(limit=20)
    assert any(i.id == row.id for i in feed2.items)


def test_clear_schedule_keeps_draft():
    from datetime import datetime, timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Signal
    from app.db.session import Base
    from app.services.admin_issue_service import AdminIssueService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    row = Signal(
        title="예약 취소 이슈 제목입니다",
        summary="예약 취소 이슈 요약입니다.",
        status="draft",
        first_seen_at=datetime.utcnow(),
        scheduled_publish_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    svc = AdminIssueService(db)
    out = svc.clear_schedule(row.id)
    assert out is not None
    assert out.status == "draft"
    assert out.scheduled_publish_at is None
    db.refresh(row)
    assert row.scheduled_publish_at is None


def test_immediate_publish_clears_schedule():
    from datetime import datetime, timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Signal
    from app.db.session import Base
    from app.services.admin_issue_service import AdminIssueService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    row = Signal(
        title="즉시 배포 이슈 제목입니다",
        summary="즉시 배포 이슈 요약입니다.",
        status="draft",
        first_seen_at=datetime.utcnow(),
        scheduled_publish_at=datetime.utcnow() + timedelta(hours=3),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    svc = AdminIssueService(db)
    out = svc.publish(row.id)
    assert out is not None
    assert out.status == "published"
    assert out.scheduled_publish_at is None
    db.refresh(row)
    assert row.scheduled_publish_at is None


def test_reject_and_unpublish_clear_schedule():
    from datetime import datetime, timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Signal
    from app.db.session import Base
    from app.services.admin_issue_service import AdminIssueService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    draft = Signal(
        title="폐기할 예약 이슈 제목입니다",
        summary="폐기할 예약 이슈 요약입니다.",
        status="draft",
        first_seen_at=datetime.utcnow(),
        scheduled_publish_at=datetime.utcnow() + timedelta(hours=1),
    )
    published = Signal(
        title="회수할 배포 이슈 제목입니다",
        summary="회수할 배포 이슈 요약입니다.",
        status="published",
        lifecycle="PUBLISHED",
        published_at=datetime.utcnow(),
        first_seen_at=datetime.utcnow(),
        scheduled_publish_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.add_all([draft, published])
    db.commit()
    db.refresh(draft)
    db.refresh(published)

    svc = AdminIssueService(db)
    rejected = svc.reject(draft.id, reason="nope")
    assert rejected is not None
    assert rejected.scheduled_publish_at is None

    unpublished = svc.unpublish(published.id)
    assert unpublished is not None
    assert unpublished.status == "draft"
    assert unpublished.scheduled_publish_at is None
