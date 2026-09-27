"""X module ON calls existing helper; OFF does not."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import DiscoveryModule
from app.db.session import Base
from app.discovery.state import ensure_seeded
from worker.jobs.ingest import run_ingest


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_x_off_does_not_call_x_helper(monkeypatch):
    db = _db()
    ensure_seeded(db)
    row = db.query(DiscoveryModule).filter(DiscoveryModule.id == "x").first()
    row.enabled = False
    db.commit()

    called = {"x": 0}

    def boom(*args, **kwargs):
        called["x"] += 1
        return 0, 0

    monkeypatch.setattr("worker.jobs.ingest.run_x_ingest", boom)
    monkeypatch.setattr("worker.jobs.ingest.active_universe", lambda db: [])
    monkeypatch.setattr(
        "worker.jobs.ingest.split_universe", lambda universe: ([], [])
    )
    result = run_ingest(db)
    assert called["x"] == 0
    assert result["fetched"] == 0


def test_x_on_calls_existing_helper(monkeypatch):
    db = _db()
    ensure_seeded(db)

    called = {"x": 0}

    def fake_x(*args, **kwargs):
        called["x"] += 1
        return 4, 3

    monkeypatch.setattr("worker.jobs.ingest.run_x_ingest", fake_x)
    monkeypatch.setattr("worker.jobs.ingest.active_universe", lambda db: [])
    monkeypatch.setattr(
        "worker.jobs.ingest.split_universe", lambda universe: ([], [])
    )
    result = run_ingest(db)
    assert called["x"] == 1
    assert result["fetched"] == 4
    assert result["inserted"] == 3
