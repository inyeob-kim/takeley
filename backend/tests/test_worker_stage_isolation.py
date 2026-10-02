"""Heavy-cycle stages fail independently. Settle needs this cycle's process."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.discovery.state import ensure_seeded, get_pipeline_controls
from worker.main import run_heavy_cycle_body


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    ensure_seeded(db)
    return db


def _patch_cycle(monkeypatch, seen: list[str], *, ingest=None, process=None):
    monkeypatch.setattr(
        "worker.main.run_ingest",
        ingest
        or (lambda db: seen.append("ingest") or {"fetched": 0, "inserted": 0, "universe": []}),
    )
    monkeypatch.setattr(
        "worker.main.run_process_signals",
        process
        or (
            lambda db: seen.append("process")
            or {"processed_raw": 0, "signals_created": 0, "meaningful_lanes": []}
        ),
    )
    monkeypatch.setattr(
        "app.pipeline.x_schedule.settle_hot_polls",
        lambda *args, **kwargs: seen.append("settle"),
    )
    monkeypatch.setattr(
        "app.pipeline.dynamic_query.settle_dynamic_polls",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.pipeline.trend_status.refresh_published_trend_statuses",
        lambda db: seen.append("trend") or 0,
    )
    monkeypatch.setattr(
        "worker.main.run_pending_push",
        lambda db: seen.append("push") or "ok",
    )
    monkeypatch.setattr("worker.main.log_rollup", lambda db, hours=24: None)


def test_ingest_failure_does_not_stop_process(monkeypatch):
    db = _db()
    seen: list[str] = []

    def boom_ingest(db):
        seen.append("ingest")
        raise RuntimeError("x rate limit")

    _patch_cycle(monkeypatch, seen, ingest=boom_ingest)
    stages = run_heavy_cycle_body(db)
    assert stages["ingest"] == "error"
    assert stages["process"] == "ok"
    assert "process" in seen
    assert "trend" in seen
    assert "push" in seen


def test_ingest_poisoned_session_is_rolled_back_before_process(monkeypatch):
    """IntegrityError during ingest must not leave process stuck on PendingRollback."""
    db = _db()
    seen: list[str] = []

    def boom_ingest(session):
        seen.append("ingest")
        from datetime import datetime

        from app.db.models import RawItem

        now = datetime.utcnow()
        session.add(
            RawItem(
                provider="official",
                external_id="dup-key",
                text="first",
                content_fingerprint="a",
                fetched_at=now,
                published_at=now,
                raw_payload={},
            )
        )
        session.flush()
        session.add(
            RawItem(
                provider="official",
                external_id="dup-key",
                text="second",
                content_fingerprint="b",
                fetched_at=now,
                published_at=now,
                raw_payload={},
            )
        )
        session.flush()

    _patch_cycle(monkeypatch, seen, ingest=boom_ingest)
    stages = run_heavy_cycle_body(db)
    assert stages["ingest"] == "error"
    assert stages["process"] == "ok"
    assert "process" in seen
    assert "push" in seen


def test_process_failure_skips_settle_keeps_trend_push(monkeypatch):
    db = _db()
    seen: list[str] = []

    def boom_process(db):
        seen.append("process")
        raise RuntimeError("process down")

    _patch_cycle(monkeypatch, seen, process=boom_process)
    stages = run_heavy_cycle_body(db)
    assert stages["process"] == "error"
    assert stages["settle"] == "skipped"
    assert "settle" not in seen
    assert "trend" in seen
    assert "push" in seen


def test_process_off_skips_process_and_settle(monkeypatch):
    db = _db()
    controls = get_pipeline_controls(db)
    controls.process_enabled = False
    db.commit()
    seen: list[str] = []
    _patch_cycle(monkeypatch, seen)
    stages = run_heavy_cycle_body(db)
    assert stages["process"] == "disabled"
    assert stages["settle"] == "skipped"
    assert "process" not in seen
    assert "ingest" in seen
    assert "trend" in seen
    assert "push" in seen


def test_trend_off_does_not_block_push(monkeypatch):
    db = _db()
    controls = get_pipeline_controls(db)
    controls.trend_enabled = False
    db.commit()
    seen: list[str] = []
    _patch_cycle(monkeypatch, seen)
    stages = run_heavy_cycle_body(db)
    assert stages["trend"] == "disabled"
    assert stages["push"] == "ok"
    assert "trend" not in seen
    assert "push" in seen
    assert "settle" in seen


def test_push_off_does_not_block_process(monkeypatch):
    db = _db()
    controls = get_pipeline_controls(db)
    controls.push_enabled = False
    db.commit()
    seen: list[str] = []
    _patch_cycle(monkeypatch, seen)
    stages = run_heavy_cycle_body(db)
    assert stages["push"] == "disabled"
    assert stages["process"] == "ok"
    assert "push" not in seen


def test_trend_failure_does_not_stop_push(monkeypatch):
    db = _db()
    seen: list[str] = []
    _patch_cycle(monkeypatch, seen)

    def boom_trend(db):
        seen.append("trend")
        raise RuntimeError("trend down")

    monkeypatch.setattr(
        "app.pipeline.trend_status.refresh_published_trend_statuses",
        boom_trend,
    )
    stages = run_heavy_cycle_body(db)
    assert stages["trend"] == "error"
    assert stages["push"] == "ok"
    assert "push" in seen
