"""Run enabled discovery modules. No source if/else in the worker loop."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.usage import record_usage
from app.db.models import DiscoveryModule
from app.discovery.protocol import IngestContext, ModuleRunResult
from app.discovery.state import mark_module_started, record_module_run, should_run_module

logger = logging.getLogger(__name__)

DISCOVERY_MODULE_RUNS = "discovery_module_runs"


def registered_modules() -> dict[str, object]:
    """Every known source is a sibling. Fetch lives in the module, not here."""
    # Late import so ingest helpers can stay in worker.jobs.ingest.
    from app.discovery.modules.hacker_news_module import HackerNewsSourceModule
    from app.discovery.modules.official_module import OfficialSourceModule
    from app.discovery.modules.reddit_module import RedditSourceModule
    from app.discovery.modules.rss_module import RssSourceModule
    from app.discovery.modules.trends_module import TrendsSourceModule
    from app.discovery.modules.x_module import XSourceModule

    return {
        "x": XSourceModule(),
        "rss": RssSourceModule(),
        "trends": TrendsSourceModule(),
        "reddit": RedditSourceModule(),
        "hacker_news": HackerNewsSourceModule(),
        "official": OfficialSourceModule(),
    }


def _implemented() -> dict[str, object]:
    """Compat alias for tests that patch the registry map."""
    return registered_modules()


def run_enabled_modules(db: Session, ctx: IngestContext) -> list[tuple[str, ModuleRunResult]]:
    """Run due modules. One exception never stops the rest."""
    registered = _implemented()
    known_ids = set(registered)
    for row in db.query(DiscoveryModule).all():
        if row.enabled and row.id not in known_ids:
            logger.warning("discovery module=%s skipped reason=unknown", row.id)

    results: list[tuple[str, ModuleRunResult]] = []
    for module_id, impl in registered.items():
        due, skip_reason = should_run_module(db, module_id)
        if not due:
            logger.info("discovery module=%s skipped reason=%s", module_id, skip_reason)
            continue
        started = datetime.utcnow()
        mark_module_started(db, module_id, started)
        try:
            result = impl.run(db, ctx)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.exception("discovery module=%s failed", module_id)
            try:
                db.rollback()
            except Exception:
                logger.exception("discovery module=%s rollback failed", module_id)
            result = ModuleRunResult(failed=1, error=str(exc)[:500])
        result.elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        record_module_run(db, module_id, started_at=started, result=result)
        record_usage(
            DISCOVERY_MODULE_RUNS,
            1,
            db=db,
            tags={
                "module": module_id,
                "status": "error" if result.error else "ok",
            },
            scope_type="shared",
        )
        if result.fetched:
            record_usage(
                "discovery_fetched",
                result.fetched,
                db=db,
                tags={"module": module_id},
                scope_type="shared",
            )
        if result.inserted:
            record_usage(
                "discovery_inserted",
                result.inserted,
                db=db,
                tags={"module": module_id},
                scope_type="shared",
            )
        logger.info(
            "discovery module=%s fetched=%s inserted=%s duplicate=%s failed=%s "
            "elapsed_ms=%s skipped=%s error=%s",
            module_id,
            result.fetched,
            result.inserted,
            result.duplicate,
            result.failed,
            result.elapsed_ms,
            result.skipped_reason,
            result.error,
        )
        results.append((module_id, result))
    return results
