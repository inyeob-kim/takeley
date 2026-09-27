"""Official discovery — SEC Atom plus optional OpenDART. Isolated per source."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.usage import DART_REQUESTS, SEC_REQUESTS, record_usage
from app.discovery.protocol import IngestContext, ModuleRunResult
from app.pipeline.markets import is_kr_equity_symbol
from app.providers.official_provider import OfficialProvider
from app.providers.sec_atom_provider import SecAtomProvider

logger = logging.getLogger(__name__)


class OfficialSourceModule:
    module_id = "official"

    def run(self, db: Session, ctx: IngestContext) -> ModuleRunResult:
        settings = get_settings()
        fetched = 0
        inserted = 0
        duplicate = 0
        failed = 0
        last_error: str | None = None

        if settings.official_sec_enabled:
            try:
                items = SecAtomProvider().fetch(limit=40)
                record_usage(
                    SEC_REQUESTS,
                    1,
                    db=db,
                    tags={"module": "official", "source": "sec"},
                    scope_type="shared",
                )
                n = ctx.raw_repo.upsert_many(items)
                fetched += len(items)
                inserted += n
                duplicate += max(0, len(items) - n)
            except Exception as exc:
                failed += 1
                last_error = str(exc)[:500]
                logger.exception("official sec failed; continuing")

        if settings.dart_api_key.strip():
            dart = OfficialProvider()
            cap = max(1, int(settings.official_dart_symbol_cap or 12))
            symbols = [u for u in ctx.kr_universe if is_kr_equity_symbol(u.symbol)][:cap]
            for entry in symbols:
                try:
                    items = dart.fetch(limit=15, symbol=entry.symbol, name=entry.name)
                    record_usage(
                        DART_REQUESTS,
                        1,
                        db=db,
                        tags={"module": "official", "source": "dart", "symbol": entry.symbol},
                        scope_type="shared",
                    )
                    n = ctx.raw_repo.upsert_many(items)
                    fetched += len(items)
                    inserted += n
                    duplicate += max(0, len(items) - n)
                except Exception as exc:
                    failed += 1
                    last_error = str(exc)[:500]
                    logger.exception("official dart symbol=%s failed; continuing", entry.symbol)

        if fetched == 0 and failed == 0 and not settings.dart_api_key.strip() and not settings.official_sec_enabled:
            return ModuleRunResult(skipped_reason="no_official_sources")

        return ModuleRunResult(
            fetched=fetched,
            inserted=inserted,
            duplicate=duplicate,
            failed=failed,
            error=last_error if failed and inserted == 0 and fetched == 0 else None,
        )
