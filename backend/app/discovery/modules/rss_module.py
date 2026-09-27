"""RSS discovery module — admin feeds, XML only, per-feed isolation."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.usage import RSS_REQUESTS, record_usage
from app.db.models import RssFeed
from app.discovery.protocol import IngestContext, ModuleRunResult
from app.providers.rss_feed_provider import RssFeedProvider

logger = logging.getLogger(__name__)


class RssSourceModule:
    module_id = "rss"

    def run(self, db: Session, ctx: IngestContext) -> ModuleRunResult:
        feeds = db.query(RssFeed).filter(RssFeed.enabled.is_(True)).all()
        if not feeds:
            return ModuleRunResult(skipped_reason="no_feeds")

        provider = RssFeedProvider()
        fetched = 0
        inserted = 0
        duplicate = 0
        failed = 0
        last_error: str | None = None

        for feed in feeds:
            feed.last_run_at = datetime.utcnow()
            try:
                result = provider.fetch_feed(
                    feed_id=feed.id,
                    url=feed.url,
                    language=feed.language or "",
                    etag=feed.etag,
                    last_modified=feed.last_modified,
                )
                record_usage(
                    RSS_REQUESTS,
                    1,
                    db=db,
                    tags={"module": "rss", "feed_id": feed.id},
                    scope_type="shared",
                )
                if result.not_modified:
                    feed.last_success_at = datetime.utcnow()
                    feed.last_error = None
                    if result.etag:
                        feed.etag = result.etag
                    if result.last_modified:
                        feed.last_modified = result.last_modified
                    db.commit()
                    continue
                n = ctx.raw_repo.upsert_many(result.items)
                fetched += len(result.items)
                inserted += n
                duplicate += max(0, len(result.items) - n)
                feed.etag = result.etag
                feed.last_modified = result.last_modified
                feed.last_success_at = datetime.utcnow()
                feed.last_error = None
                db.commit()
            except Exception as exc:
                failed += 1
                last_error = str(exc)[:500]
                feed.last_error = last_error
                feed.error_count = int(feed.error_count or 0) + 1
                db.commit()
                logger.exception("rss feed=%s failed; continuing", feed.id)

        return ModuleRunResult(
            fetched=fetched,
            inserted=inserted,
            duplicate=duplicate,
            failed=failed,
            error=last_error if failed and inserted == 0 and fetched == 0 else None,
        )
