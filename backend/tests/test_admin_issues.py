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


def test_published_issue_cannot_be_edited():
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
        title="배포된 이슈 제목입니다",
        summary="배포된 이슈 요약입니다.",
        status="published",
        published_at=datetime.utcnow(),
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
        assert "published_issue_cannot_edit" in str(exc)
    assert raised
    db.refresh(row)
    assert row.column_body == "원래 칼럼"
