"""Worker entrypoint: ingest → Issue process → push."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Allow `python -m worker.main` from backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.core.logging import configure_logging, local_now_iso, utc_now_iso
from app.core.usage import bind_usage_db, log_rollup, reset_usage_db
from app.db.session import SessionLocal, init_db
from worker.jobs.ingest import run_ingest
from worker.jobs.process_signals import run_process_signals
from worker.jobs.publish_scheduled import run_publish_scheduled
from worker.jobs.send_push import run_pending_push
from worker.scheduler import JobScheduler

level = configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
logger.info(
    "worker logging ready level=%s environment=%s debug=%s "
    "test_fast_ingest=%s ingest_interval_s=%s",
    logging.getLevelName(level),
    settings.environment,
    settings.debug,
    settings.test_fast_ingest,
    settings.ingest_interval_seconds,
)
if settings.test_fast_ingest:
    logger.warning(
        "TEST_FAST_INGEST=true — all source fetch intervals clamped to %ss",
        settings.test_ingest_interval_seconds,
    )


def run_isolated_stage(name: str, fn):
    """Run one heavy-cycle stage. Exception is logged; later stages may continue."""
    try:
        return fn(), None
    except Exception as exc:
        logger.exception("%s stage failed", name)
        return None, exc


def run_heavy_cycle_body(db) -> dict:
    """One heavy cycle against an open session. Stages fail independently."""
    from app.discovery.state import get_pipeline_controls

    controls = get_pipeline_controls(db)
    stages: dict[str, str] = {}

    t = time.monotonic()
    ingest_result, ingest_err = run_isolated_stage("ingest", lambda: run_ingest(db))
    if ingest_err is not None:
        stages["ingest"] = "error"
    else:
        stages["ingest"] = "ok"
        logger.info(
            "ingest summary fetched=%s inserted=%s universe=%s elapsed_s=%.1f",
            ingest_result.get("fetched"),
            ingest_result.get("inserted"),
            ingest_result.get("universe"),
            time.monotonic() - t,
        )
        logger.debug("ingest detail=%s", ingest_result)

    process_result = None
    if not controls.process_enabled:
        stages["process"] = "disabled"
        logger.info("process skipped reason=disabled")
    else:
        t = time.monotonic()
        process_result, process_err = run_isolated_stage(
            "process", lambda: run_process_signals(db)
        )
        if process_err is not None:
            stages["process"] = "error"
            try:
                db.rollback()
            except Exception:
                logger.exception("process rollback failed")
        else:
            stages["process"] = "ok"
            logger.info(
                "process summary raw=%s events=%s created=%s rejected=%s "
                "published_today=%s quota_remaining=%s elapsed_s=%.1f",
                process_result.get("processed_raw"),
                process_result.get("events_upserted"),
                process_result.get("signals_created"),
                process_result.get("signals_rejected"),
                process_result.get("published_today"),
                process_result.get("quota_remaining"),
                time.monotonic() - t,
            )
            logger.debug("process detail=%s", process_result)

    # settle_hot/dynamic need this cycle's meaningful_lanes from process.
    if process_result is None:
        stages["settle"] = "skipped"
        logger.info("settle skipped reason=process_unavailable")
    else:
        def _settle() -> None:
            from app.db.repositories import CursorRepository
            from app.pipeline.dynamic_query import settle_dynamic_polls
            from app.pipeline.x_schedule import settle_hot_polls
            from app.services.x_ingest_admin import (
                get_or_create as get_x_ingest_config,
            )

            x_config = get_x_ingest_config(db)
            settle_hot_polls(
                CursorRepository(db),
                meaningful=set(process_result.get("meaningful_lanes") or []),
                idle_limit=int(x_config.hot_idle_scans or 2),
            )
            settle_dynamic_polls(
                CursorRepository(db),
                meaningful=set(process_result.get("meaningful_lanes") or []),
                idle_limit=int(x_config.hot_idle_scans or 2),
            )

        _, settle_err = run_isolated_stage("settle", _settle)
        stages["settle"] = "error" if settle_err is not None else "ok"

    # Trend reads published Issues only — does not need this cycle's process.
    if not controls.trend_enabled:
        stages["trend"] = "disabled"
        logger.info("trend skipped reason=disabled")
    else:
        t = time.monotonic()

        def _trend() -> int:
            from app.pipeline.trend_status import refresh_published_trend_statuses

            return refresh_published_trend_statuses(db)

        refreshed, trend_err = run_isolated_stage("trend", _trend)
        if trend_err is not None:
            stages["trend"] = "error"
        else:
            stages["trend"] = "ok"
            logger.info(
                "trend refresh published=%s elapsed_s=%.1f",
                refreshed,
                time.monotonic() - t,
            )

    # Scheduled admin publishes before push so enqueue lands in this cycle.
    t = time.monotonic()
    sched_result, sched_err = run_isolated_stage(
        "scheduled_publish", lambda: run_publish_scheduled(db)
    )
    if sched_err is not None:
        stages["scheduled_publish"] = "error"
    else:
        stages["scheduled_publish"] = "ok"
        logger.info(
            "scheduled_publish summary result=%s elapsed_s=%.1f",
            sched_result,
            time.monotonic() - t,
        )

    if not controls.push_enabled:
        stages["push"] = "disabled"
        logger.info("push skipped reason=disabled")
    else:
        t = time.monotonic()
        push_result, push_err = run_isolated_stage(
            "push", lambda: run_pending_push(db)
        )
        if push_err is not None:
            stages["push"] = "error"
        else:
            stages["push"] = "ok"
            logger.info(
                "push summary result=%s elapsed_s=%.1f",
                push_result,
                time.monotonic() - t,
            )

    run_isolated_stage("rollup", lambda: log_rollup(db, hours=24))
    return stages


def run_heavy_cycle() -> None:
    """Ingest + Issue process + pending push (+ rollup)."""
    init_db()
    db = SessionLocal()
    usage_token = bind_usage_db(db)
    t0 = time.monotonic()
    try:
        logger.info(
            "heavy cycle work begin local=%s utc=%s",
            local_now_iso(),
            utc_now_iso(),
        )
        run_heavy_cycle_body(db)
        logger.info(
            "heavy cycle work done total_elapsed_s=%.1f local=%s utc=%s",
            time.monotonic() - t0,
            local_now_iso(),
            utc_now_iso(),
        )
    finally:
        reset_usage_db(usage_token)
        db.close()


# Back-compat alias for scripts that still call run_cycle().
def run_cycle() -> None:
    run_heavy_cycle()


def _scheduled_wake_seconds() -> int:
    """Scheduled mode checks slots often. X is still skipped outside a slot."""
    from app.db.session import SessionLocal
    from app.services.x_ingest_admin import get_or_create as get_x_ingest_config

    init_db()
    db = SessionLocal()
    try:
        config = get_x_ingest_config(db)
        if config.scan_mode == "scheduled":
            return 15 * 60
    except Exception:
        logger.exception("x ingest config unavailable; keeping ingest interval")
    finally:
        db.close()
    return settings.ingest_interval_seconds


def main(once: bool = False) -> None:
    if once or "--once" in sys.argv:
        logger.info("worker mode=once")
        run_heavy_cycle()
        return

    wake_seconds = _scheduled_wake_seconds()
    logger.info(
        "worker mode=forever heavy_interval_s=%s",
        wake_seconds,
    )
    heavy = JobScheduler(
        interval_seconds=wake_seconds,
        name="heavy_cycle",
    )
    heavy.run_forever(run_heavy_cycle)


if __name__ == "__main__":
    main()
