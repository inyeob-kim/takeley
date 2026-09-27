"""Hacker News discovery — top stories via the public Firebase API."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.usage import HN_REQUESTS, record_usage
from app.discovery.protocol import IngestContext, ModuleRunResult
from app.providers.hacker_news_provider import HackerNewsProvider


class HackerNewsSourceModule:
    module_id = "hacker_news"

    def run(self, db: Session, ctx: IngestContext) -> ModuleRunResult:
        limit = int(get_settings().hn_top_limit or 30)
        items = HackerNewsProvider().fetch_top(limit=limit)
        record_usage(
            HN_REQUESTS,
            1,
            db=db,
            tags={"module": "hacker_news"},
            scope_type="shared",
        )
        n = ctx.raw_repo.upsert_many(items)
        return ModuleRunResult(
            fetched=len(items),
            inserted=n,
            duplicate=max(0, len(items) - n),
        )
