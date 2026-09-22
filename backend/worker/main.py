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

        t = time.monotonic()
        ingest_result = run_ingest(db)
        logger.info(
            "ingest summary fetched=%s inserted=%s universe=%s elapsed_s=%.1f",
            ingest_result.get("fetched"),
            ingest_result.get("inserted"),
            ingest_result.get("universe"),
            time.monotonic() - t,
        )
        logger.debug("ingest detail=%s", ingest_result)

        t = time.monotonic()
        process_result = run_process_signals(db)
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

        t = time.monotonic()
        from app.pipeline.trend_status import refresh_published_trend_statuses

        refreshed = refresh_published_trend_statuses(db)
        logger.info(
            "trend refresh published=%s elapsed_s=%.1f",
            refreshed,
            time.monotonic() - t,
        )

        t = time.monotonic()
        push_result = run_pending_push(db)
        logger.info(
            "push summary result=%s elapsed_s=%.1f",
            push_result,
            time.monotonic() - t,
        )

        log_rollup(db, hours=24)

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


def main(once: bool = False) -> None:
    if once or "--once" in sys.argv:
        logger.info("worker mode=once")
        run_heavy_cycle()
        return

    logger.info(
        "worker mode=forever heavy_interval_s=%s",
        settings.ingest_interval_seconds,
    )
    heavy = JobScheduler(
        interval_seconds=settings.ingest_interval_seconds,
        name="heavy_cycle",
    )
    heavy.run_forever(run_heavy_cycle)


if __name__ == "__main__":
    main()
