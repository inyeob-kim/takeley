"""Admin discovery APIs against an isolated SQLite DB."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.session import Base, get_db
from app.main import app


def _client(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret-test-key")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def _override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)
    return client, get_settings


def test_discovery_modules_and_pipeline(monkeypatch):
    client, settings = _client(monkeypatch)
    headers = {"X-Admin-Key": "secret-test-key"}
    try:
        r = client.get("/api/v1/admin/discovery/modules", headers=headers)
        assert r.status_code == 200
        ids = [row["id"] for row in r.json()]
        assert ids[:6] == ["x", "rss", "trends", "reddit", "hacker_news", "official"]
        by_id = {row["id"]: row for row in r.json()}
        assert by_id["x"]["enabled"] is True
        assert by_id["x"]["implemented"] is True
        assert by_id["rss"]["implemented"] is True
        assert by_id["rss"]["enabled"] is False
        assert by_id["trends"]["implemented"] is True
        assert by_id["reddit"]["implemented"] is True
        assert by_id["hacker_news"]["implemented"] is True
        assert by_id["official"]["implemented"] is True
        assert by_id["official"]["enabled"] is False

        r2 = client.put(
            "/api/v1/admin/discovery/modules",
            headers=headers,
            json=[{"id": "x", "enabled": False}, {"id": "rss", "enabled": True}],
        )
        assert r2.status_code == 200
        by_id = {row["id"]: row for row in r2.json()}
        assert by_id["x"]["enabled"] is False
        assert by_id["rss"]["enabled"] is True

        pipe = client.get("/api/v1/admin/discovery/pipeline", headers=headers)
        assert pipe.status_code == 200
        assert pipe.json()["process_enabled"] is True

        off = client.put(
            "/api/v1/admin/discovery/pipeline",
            headers=headers,
            json={"process_enabled": False},
        )
        assert off.json()["process_enabled"] is False
    finally:
        app.dependency_overrides.clear()
        settings.cache_clear()


def test_empty_rss_list_seeds_defaults(monkeypatch):
    client, settings = _client(monkeypatch)
    headers = {"X-Admin-Key": "secret-test-key"}
    try:
        listed = client.get("/api/v1/admin/discovery/rss-feeds", headers=headers)
        assert listed.status_code == 200
        names = {row["name"] for row in listed.json()}
        assert "BBC News" in names
        assert "Google News" in names
        assert "연합뉴스TV" in names
    finally:
        app.dependency_overrides.clear()
        settings.cache_clear()


def test_rss_feed_crud_and_url_validation(monkeypatch):
    client, settings = _client(monkeypatch)
    headers = {"X-Admin-Key": "secret-test-key"}
    try:
        bad = client.post(
            "/api/v1/admin/discovery/rss-feeds",
            headers=headers,
            json={"name": "Bad", "url": "ftp://nope"},
        )
        assert bad.status_code == 400

        created = client.post(
            "/api/v1/admin/discovery/rss-feeds",
            headers=headers,
            json={"name": "Demo", "url": "https://example.com/rss.xml"},
        )
        assert created.status_code == 200
        feed_id = created.json()["id"]

        listed = client.get("/api/v1/admin/discovery/rss-feeds", headers=headers)
        assert any(row["id"] == feed_id for row in listed.json())

        patched = client.patch(
            f"/api/v1/admin/discovery/rss-feeds/{feed_id}",
            headers=headers,
            json={"enabled": False},
        )
        assert patched.json()["enabled"] is False

        deleted = client.delete(
            f"/api/v1/admin/discovery/rss-feeds/{feed_id}",
            headers=headers,
        )
        assert deleted.status_code == 200
    finally:
        app.dependency_overrides.clear()
        settings.cache_clear()
