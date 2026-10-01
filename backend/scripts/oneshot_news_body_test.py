"""Prod smoke: RSS body enrich → one NEWS card with real article text."""

from __future__ import annotations

import logging
import os
import sys

os.environ["NEWS_PIPELINE_ENABLED"] = "true"
os.environ["NEWS_AUTO_PUBLISH"] = "true"
os.environ["DAILY_NEWS_CAP"] = "5"
os.environ["NEWS_LLM_BUDGET_PER_CYCLE"] = "8"
os.environ["ISSUE_LLM_UNDERSTAND_BUDGET_PER_CYCLE"] = "2"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from sqlalchemy import text

from app.core.config import get_settings
from app.db.models import RawItem, RssFeed
from app.db.session import SessionLocal
from app.pipeline.normalize import content_fingerprint, normalize_text
from app.providers.rss_feed_provider import RssFeedProvider
from worker.jobs.process_issues_v2 import run_process_issues_v2

get_settings.cache_clear()


def main() -> int:
    settings = get_settings()
    print("news_fetch_body=", settings.news_fetch_body)
    print("news_pipeline_enabled=", settings.news_pipeline_enabled)

    db = SessionLocal()
    try:
        feeds = (
            db.query(RssFeed)
            .filter(RssFeed.enabled.is_(True))
            .order_by(RssFeed.last_success_at.desc().nullslast())
            .all()
        )
        if not feeds:
            print("FAIL: no enabled rss feed")
            return 1

        # Prefer direct publisher feeds; Google News needs batchexecute resolve.
        feeds = sorted(
            feeds,
            key=lambda f: (
                0 if "news.google." not in (f.url or "") else 1,
                f.name or "",
            ),
        )

        provider = RssFeedProvider()
        result = None
        feed = None
        for candidate in feeds:
            print("try_feed=", candidate.name, candidate.url)
            result = provider.fetch_feed(
                feed_id=candidate.id,
                url=candidate.url,
                language=candidate.language or "",
                limit=8,
            )
            print("  kept=", len(result.items))
            if result.items:
                feed = candidate
                break
        if not feed or not result or not result.items:
            print("FAIL: no body-enriched items from any feed")
            return 2

        print("feed=", feed.id, feed.url)
        sample = result.items[0]
        body_ok = bool((sample.raw_payload or {}).get("body_ok"))
        print("sample_title=", (sample.title or "")[:100])
        print("sample_url=", (sample.url or "")[:180])
        print("body_ok=", body_ok, "text_chars=", len(sample.text or ""))
        print("text_preview=")
        print((sample.text or "")[:600])
        print("---")
        if not body_ok or len(sample.text or "") < 280:
            print("FAIL: body enrich did not produce article text")
            return 2

        fp = content_fingerprint(
            normalize_text(
                f"{sample.title}. {sample.text}" if sample.title else sample.text
            )
        )
        row = (
            db.query(RawItem)
            .filter(
                RawItem.provider == sample.provider.value,
                RawItem.external_id == sample.external_id,
            )
            .one_or_none()
        )
        if row is None:
            row = RawItem(
                provider=sample.provider.value,
                external_id=sample.external_id,
                url=sample.url,
                author=sample.author,
                title=sample.title,
                text=sample.text,
                language=sample.language,
                published_at=sample.published_at,
                fetched_at=sample.fetched_at,
                raw_payload=sample.raw_payload,
                content_fingerprint=fp,
                processed=0,
            )
            db.add(row)
            print("raw_action=insert")
        else:
            row.url = sample.url
            row.title = sample.title
            row.text = sample.text
            row.raw_payload = sample.raw_payload
            row.content_fingerprint = fp
            row.fetched_at = sample.fetched_at
            row.processed = 0
            print("raw_action=update", row.id)
        db.commit()

        before = db.execute(
            text("SELECT count(*) FROM issues WHERE content_kind = 'NEWS'")
        ).scalar()
        process = run_process_issues_v2(db, limit=40)
        print("process=", process)

        rows = db.execute(
            text(
                """
                SELECT id::text, status, left(title, 100), left(summary, 260)
                FROM issues
                WHERE content_kind = 'NEWS'
                ORDER BY first_seen_at DESC NULLS LAST
                LIMIT 3
                """
            )
        ).fetchall()
        print("=== latest NEWS ===")
        for r in rows:
            print(r)

        after = db.execute(
            text("SELECT count(*) FROM issues WHERE content_kind = 'NEWS'")
        ).scalar()
        print("news_before=", before, "news_after=", after)
        created = int(after or 0) - int(before or 0)
        print("news_created_this_run=", created)
        return 0 if created >= 1 or int(after or 0) >= 1 else 3
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
