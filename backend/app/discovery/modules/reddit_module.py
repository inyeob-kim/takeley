"""Reddit discovery — public hot listings, one subreddit failure does not stop others."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.usage import REDDIT_REQUESTS, record_usage
from app.discovery.protocol import IngestContext, ModuleRunResult
from app.discovery.relevance import filter_issue_relevant
from app.providers.reddit_provider import RedditProvider

logger = logging.getLogger(__name__)


def _subreddits() -> list[str]:
    raw = get_settings().reddit_subreddits
    return [part.strip().lstrip("r/") for part in raw.split(",") if part.strip()]


class RedditSourceModule:
    module_id = "reddit"

    def run(self, db: Session, ctx: IngestContext) -> ModuleRunResult:
        subs = _subreddits()
        if not subs:
            return ModuleRunResult(skipped_reason="no_subreddits")

        provider = RedditProvider()
        if not provider.configured():
            return ModuleRunResult(skipped_reason="no_credentials")
        limit = int(get_settings().reddit_limit_per_sub or 15)
        fetched = 0
        inserted = 0
        duplicate = 0
        failed = 0
        last_error: str | None = None

        for sub in subs:
            try:
                items = filter_issue_relevant(provider.fetch_subreddit(sub, limit=limit))
                record_usage(
                    REDDIT_REQUESTS,
                    1,
                    db=db,
                    tags={"module": "reddit", "subreddit": sub},
                    scope_type="shared",
                )
                n = ctx.raw_repo.upsert_many(items)
                fetched += len(items)
                inserted += n
                duplicate += max(0, len(items) - n)
            except Exception as exc:
                failed += 1
                last_error = str(exc)[:500]
                logger.exception("reddit subreddit=%s failed; continuing", sub)

        return ModuleRunResult(
            fetched=fetched,
            inserted=inserted,
            duplicate=duplicate,
            failed=failed,
            error=last_error if failed and inserted == 0 and fetched == 0 else None,
        )
