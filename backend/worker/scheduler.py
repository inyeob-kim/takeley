from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.logging import local_now_iso, utc_now_iso

logger = logging.getLogger(__name__)


class JobScheduler:
    """Simple interval loop for MVP. Replace with Celery/RQ later if needed."""

    def __init__(
        self,
        interval_seconds: int | None = None,
        *,
        name: str = "cycle",
    ) -> None:
        settings = get_settings()
        self.name = name
        self.interval_seconds = interval_seconds or settings.ingest_interval_seconds
        # Heartbeat while sleeping (DEBUG). Cap so long intervals stay quiet enough.
        self._heartbeat_seconds = min(60, max(10, self.interval_seconds // 30 or 60))

    def run_forever(self, tick) -> None:
        logger.info(
            "%s scheduler started interval_s=%s (~%s min) local=%s utc=%s",
            self.name,
            self.interval_seconds,
            round(self.interval_seconds / 60, 1),
            local_now_iso(),
            utc_now_iso(),
        )
        cycle = 0
        while True:
            cycle += 1
            started = time.monotonic()
            started_at = datetime.now(timezone.utc)
            logger.info(
                "%s#%s start local=%s utc=%s interval_s=%s",
                self.name,
                cycle,
                local_now_iso(),
                utc_now_iso(),
                self.interval_seconds,
            )
            try:
                tick()
            except Exception:
                logger.exception("%s tick failed cycle=%s", self.name, cycle)

            elapsed = time.monotonic() - started
            next_at = started_at + timedelta(seconds=self.interval_seconds)
            # Sleep the remainder of the interval (not interval after work finishes),
            # so cadence stays close to wall-clock period.
            remaining = max(0.0, self.interval_seconds - elapsed)
            logger.info(
                "%s#%s end elapsed_s=%.1f next_cycle_at_utc=%s sleep_s=%.0f",
                self.name,
                cycle,
                elapsed,
                next_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                remaining,
            )
            self._sleep_with_countdown(remaining, cycle=cycle)

    def _sleep_with_countdown(self, remaining: float, *, cycle: int) -> None:
        deadline = time.monotonic() + remaining
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return
            chunk = min(self._heartbeat_seconds, left)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "%s#%s waiting remaining_s=%.0f (~%.1f min)",
                    self.name,
                    cycle,
                    left,
                    left / 60,
                )
            time.sleep(chunk)
