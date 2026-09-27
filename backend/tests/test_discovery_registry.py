"""Discovery registry, X ON/OFF, worker stage isolation."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import DiscoveryModule, RssFeed
from app.db.session import Base
from app.discovery.protocol import IngestContext, ModuleRunResult
from app.discovery.registry import run_enabled_modules
from app.discovery.state import DEFAULT_RSS_FEEDS, ensure_seeded, is_module_enabled
from worker.main import run_isolated_stage


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _ctx(db):
    from app.db.repositories import CursorRepository, RawItemRepository

    return IngestContext(
        raw_repo=RawItemRepository(db),
        cursor_repo=CursorRepository(db),
        universe=[],
        us_universe=[],
        kr_universe=[],
    )


def test_seed_enables_x_only():
    db = _session()
    ensure_seeded(db)
    assert is_module_enabled(db, "x") is True
    assert is_module_enabled(db, "rss") is False
    assert is_module_enabled(db, "trends") is False
    feeds = db.query(RssFeed).order_by(RssFeed.name.asc()).all()
    assert [feed.name for feed in feeds] == sorted(spec["name"] for spec in DEFAULT_RSS_FEEDS)
    assert all(feed.enabled for feed in feeds)


def test_seed_does_not_replace_existing_rss_feeds():
    db = _session()
    ensure_seeded(db)
    db.add(RssFeed(name="Custom", url="https://example.com/rss.xml", enabled=True))
    db.commit()
    # Second seed after a wipe of defaults would still keep Custom if any row exists.
    db.query(RssFeed).filter(RssFeed.name != "Custom").delete()
    db.commit()
    ensure_seeded(db)
    names = [feed.name for feed in db.query(RssFeed).all()]
    assert names == ["Custom"]


def test_disabled_module_skipped(monkeypatch):
    db = _session()
    ensure_seeded(db)
    row = db.query(DiscoveryModule).filter(DiscoveryModule.id == "x").first()
    row.enabled = False
    db.commit()

    called = {"x": 0}

    class FakeX:
        module_id = "x"

        def run(self, db, ctx):
            called["x"] += 1
            return ModuleRunResult(fetched=1)

    monkeypatch.setattr(
        "app.discovery.registry._implemented",
        lambda: {"x": FakeX()},
    )
    results = run_enabled_modules(db, _ctx(db))
    assert results == []
    assert called["x"] == 0


def test_enabled_module_runs(monkeypatch):
    db = _session()
    ensure_seeded(db)

    class FakeX:
        module_id = "x"

        def run(self, db, ctx):
            return ModuleRunResult(fetched=3, inserted=2)

    monkeypatch.setattr(
        "app.discovery.registry._implemented",
        lambda: {"x": FakeX()},
    )
    results = run_enabled_modules(db, _ctx(db))
    assert results[0][0] == "x"
    assert results[0][1].fetched == 3
    row = db.query(DiscoveryModule).filter(DiscoveryModule.id == "x").first()
    assert row.last_status == "ok"
    assert row.items_fetched == 3


def test_module_exception_does_not_stop_next(monkeypatch):
    db = _session()
    ensure_seeded(db)
    rss = db.query(DiscoveryModule).filter(DiscoveryModule.id == "rss").first()
    rss.enabled = True
    db.commit()
    seen = []

    class Boom:
        module_id = "x"

        def run(self, db, ctx):
            seen.append("x")
            raise RuntimeError("x down")

    class Ok:
        module_id = "rss"

        def run(self, db, ctx):
            seen.append("rss")
            return ModuleRunResult(fetched=1, inserted=1)

    monkeypatch.setattr(
        "app.discovery.registry._implemented",
        lambda: {"x": Boom(), "rss": Ok()},
    )
    results = run_enabled_modules(db, _ctx(db))
    assert seen == ["x", "rss"]
    by_id = dict(results)
    assert by_id["x"].error
    assert by_id["rss"].inserted == 1


def test_unknown_module_not_executed():
    db = _session()
    ensure_seeded(db)
    x = db.query(DiscoveryModule).filter(DiscoveryModule.id == "x").first()
    x.enabled = False
    db.add(DiscoveryModule(id="not_a_real_module", enabled=True))
    db.commit()
    results = run_enabled_modules(db, _ctx(db))
    assert all(module_id != "not_a_real_module" for module_id, _ in results)


def test_enabled_unknown_registered_module_is_safe(monkeypatch):
    db = _session()
    ensure_seeded(db)
    x = db.query(DiscoveryModule).filter(DiscoveryModule.id == "x").first()
    x.enabled = False
    db.commit()

    class Quiet:
        module_id = "trends"

        def run(self, db, ctx):
            return ModuleRunResult(skipped_reason="not_implemented")

    monkeypatch.setattr(
        "app.discovery.registry._implemented",
        lambda: {"trends": Quiet()},
    )
    trends = db.query(DiscoveryModule).filter(DiscoveryModule.id == "trends").first()
    trends.enabled = True
    db.commit()
    results = dict(run_enabled_modules(db, _ctx(db)))
    assert results["trends"].skipped_reason == "not_implemented"
    assert results["trends"].error is None


def test_rss_interval_skips_until_due(monkeypatch):
    from datetime import datetime, timedelta

    db = _session()
    ensure_seeded(db)
    x = db.query(DiscoveryModule).filter(DiscoveryModule.id == "x").first()
    x.enabled = False
    rss = db.query(DiscoveryModule).filter(DiscoveryModule.id == "rss").first()
    rss.enabled = True
    rss.interval_seconds = 3600
    rss.last_finished_at = datetime.utcnow() - timedelta(minutes=10)
    db.commit()
    called = {"rss": 0}

    class FakeRss:
        module_id = "rss"

        def run(self, db, ctx):
            called["rss"] += 1
            return ModuleRunResult(fetched=1)

    monkeypatch.setattr(
        "app.discovery.registry._implemented",
        lambda: {"rss": FakeRss()},
    )
    assert run_enabled_modules(db, _ctx(db)) == []
    assert called["rss"] == 0

    rss.last_finished_at = datetime.utcnow() - timedelta(hours=2)
    db.commit()
    results = run_enabled_modules(db, _ctx(db))
    assert called["rss"] == 1
    assert results[0][1].fetched == 1


def test_rss_off_does_not_run_module(monkeypatch):
    db = _session()
    ensure_seeded(db)
    x = db.query(DiscoveryModule).filter(DiscoveryModule.id == "x").first()
    x.enabled = False
    db.commit()
    called = {"rss": 0}

    class FakeRss:
        module_id = "rss"

        def run(self, db, ctx):
            called["rss"] += 1
            return ModuleRunResult(fetched=9)

    monkeypatch.setattr(
        "app.discovery.registry._implemented",
        lambda: {"rss": FakeRss()},
    )
    assert run_enabled_modules(db, _ctx(db)) == []
    assert called["rss"] == 0


def test_run_isolated_stage_continues():
    ok, err = run_isolated_stage("ok", lambda: 7)
    assert ok == 7
    assert err is None
    failed, err = run_isolated_stage("boom", lambda: (_ for _ in ()).throw(ValueError("no")))
    assert failed is None
    assert err is not None
