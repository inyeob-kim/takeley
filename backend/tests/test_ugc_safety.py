"""App Store 1.2 UGC: filter, hide, block, report, eject."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import IssueComment, ParticipationOption, Signal, User
from app.db.session import Base, get_db
from app.main import app


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _client(db):
    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _users(db):
    author = User(device_id="author-device", platform="ios")
    viewer = User(device_id="viewer-device", platform="ios")
    db.add_all([author, viewer])
    db.commit()
    db.refresh(author)
    db.refresh(viewer)
    return author, viewer


def _issue_with_comment(db, author_id: str, content: str = "괜찮은 생각") -> tuple[Signal, IssueComment]:
    signal = Signal(
        title="UGC 이슈",
        summary="요약",
        status="published",
        published_at=datetime.utcnow(),
        participation_suitable=True,
        participation_question="어느 쪽?",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    db.add(ParticipationOption(signal_id=signal.id, label="이쪽", display_order=0))
    comment = IssueComment(
        signal_id=signal.id,
        user_id=author_id,
        content=content,
        status="visible",
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return signal, comment


def test_comment_filter_and_hide_block_report():
    db = _session()
    author, viewer = _users(db)
    signal, comment = _issue_with_comment(db, author.id)
    client = _client(db)

    blocked = client.post(
        f"/api/v1/issues/{signal.id}/comments",
        json={"content": "이건 씨발 안 됨", "user_id": viewer.id},
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "objectionable_content"

    listed = client.get(
        f"/api/v1/issues/{signal.id}/comments",
        params={"user_id": viewer.id},
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    hidden = client.post(
        "/api/v1/safety/hide",
        json={"target_type": "comment", "target_id": comment.id, "user_id": viewer.id},
    )
    assert hidden.status_code == 200
    after_hide = client.get(
        f"/api/v1/issues/{signal.id}/comments",
        params={"user_id": viewer.id},
    )
    assert after_hide.json()["count"] == 0

    other, extra = _issue_with_comment(db, author.id, "두번째")
    blocked_user = client.post(
        "/api/v1/safety/block",
        json={"blocked_user_id": author.id, "user_id": viewer.id},
    )
    assert blocked_user.status_code == 200
    after_block = client.get(
        f"/api/v1/issues/{other.id}/comments",
        params={"user_id": viewer.id},
    )
    assert after_block.json()["count"] == 0

    reporter = User(device_id="reporter-device", platform="ios")
    db.add(reporter)
    db.commit()
    db.refresh(reporter)
    flagged, row = _issue_with_comment(db, author.id, "신고 대상")
    reported = client.post(
        "/api/v1/safety/report",
        json={
            "target_type": "comment",
            "target_id": row.id,
            "reason": "hate",
            "user_id": reporter.id,
        },
    )
    assert reported.status_code == 200
    for_reporter = client.get(
        f"/api/v1/issues/{flagged.id}/comments",
        params={"user_id": reporter.id},
    )
    assert for_reporter.json()["count"] == 0

    app.dependency_overrides.clear()


def test_delete_own_comment_drops_count_and_activity():
    db = _session()
    author, _viewer = _users(db)
    signal, comment = _issue_with_comment(db, author.id, "지울 댓글")
    client = _client(db)

    before = client.get(f"/api/v1/issues/{signal.id}").json()
    assert before["comment_count"] == 1

    deleted = client.delete(
        f"/api/v1/safety/comments/{comment.id}",
        params={"user_id": author.id},
    )
    assert deleted.status_code == 200

    after = client.get(f"/api/v1/issues/{signal.id}").json()
    assert after["comment_count"] == 0
    listed = client.get(f"/api/v1/issues/{signal.id}/comments").json()
    assert listed["count"] == 0

    activity = client.get(
        "/api/v1/issues/activity/me",
        params={"user_id": author.id},
    )
    assert activity.status_code == 200
    assert activity.json()["comments"] == []

    app.dependency_overrides.clear()


def test_admin_remove_and_eject():
    db = _session()
    author, viewer = _users(db)
    signal, comment = _issue_with_comment(db, author.id, "내려야 할 글")
    client = _client(db)

    client.post(
        "/api/v1/safety/report",
        json={
            "target_type": "comment",
            "target_id": comment.id,
            "reason": "violence",
            "user_id": viewer.id,
        },
    )

    from app.services.safety_service import SafetyService

    reports = SafetyService(db).list_reports(status="open")
    assert len(reports) == 1
    resolved = SafetyService(db).resolve(reports[0].id, action="remove", eject=True)
    assert resolved.status == "removed"
    db.refresh(author)
    db.refresh(comment)
    assert author.status == "suspended"
    assert comment.status == "removed"

    denied = client.post(
        f"/api/v1/issues/{signal.id}/comments",
        json={"content": "다시 쓸게요", "user_id": author.id},
    )
    assert denied.status_code == 400
    assert denied.json()["detail"] == "user_inactive"

    app.dependency_overrides.clear()
