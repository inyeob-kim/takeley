"""Search Trends discovery — Google Trends RSS per geo, isolated."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.usage import TRENDS_REQUESTS, record_usage
from app.discovery.protocol import IngestContext, ModuleRunResult
from app.discovery.relevance import filter_issue_relevant
from app.providers.trends_provider import TrendsProvider

logger = logging.getLogger(__name__)


def _geos() -> list[str]:
    raw = get_settings().trends_geos
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


class TrendsSourceModule:
    module_id = "trends"

    def run(self, db: Session, ctx: IngestContext) -> ModuleRunResult:
        geos = _geos()
        if not geos:
            return ModuleRunResult(skipped_reason="no_geos")

        provider = TrendsProvider()
        fetched = 0
        inserted = 0
        duplicate = 0
        failed = 0
        last_error: str | None = None

        for geo in geos:
            try:
                items = filter_issue_relevant(provider.fetch_geo(geo))
                record_usage(
                    TRENDS_REQUESTS,
                    1,
                    db=db,
                    tags={"module": "trends", "geo": geo},
                    scope_type="shared",
                )
                n = ctx.raw_repo.upsert_many(items)
                fetched += len(items)
                inserted += n
                duplicate += max(0, len(items) - n)
            except Exception as exc:
                failed += 1
                last_error = str(exc)[:500]
                logger.exception("trends geo=%s failed; continuing", geo)

        return ModuleRunResult(
            fetched=fetched,
            inserted=inserted,
            duplicate=duplicate,
            failed=failed,
            error=last_error if failed and inserted == 0 and fetched == 0 else None,
        )
