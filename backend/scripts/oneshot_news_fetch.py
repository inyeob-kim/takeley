"""One-shot: process until at most 1 NEWS card is created (test helper)."""

from __future__ import annotations

import logging
import os
import sys

# Force NEWS path for this process only (does not rewrite server env file).
os.environ["NEWS_PIPELINE_ENABLED"] = "true"
os.environ["NEWS_AUTO_PUBLISH"] = "true"
os.environ["DAILY_NEWS_CAP"] = "1"
os.environ["NEWS_LLM_BUDGET_PER_CYCLE"] = "8"
os.environ["ISSUE_LLM_UNDERSTAND_BUDGET_PER_CYCLE"] = "4"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from worker.jobs.process_issues_v2 import run_process_issues_v2

get_settings.cache_clear()
settings = get_settings()
print("news_pipeline_enabled=", settings.news_pipeline_enabled)
print("news_auto_publish=", settings.news_auto_publish)
print("daily_news_cap=", settings.daily_news_cap)


def main() -> int:
    db = SessionLocal()
    try:
        before = db.execute(
            text("SELECT count(*) FROM issues WHERE content_kind = 'NEWS'")
        ).scalar()
        unprocessed = db.execute(
            text("SELECT count(*) FROM raw_items WHERE processed = 0")
        ).scalar()
        print("news_before=", before, "unprocessed_raw=", unprocessed)

        result = run_process_issues_v2(db, limit=80)
        print("process_result=", result)

        rows = db.execute(
            text(
                """
                SELECT id::text, status, content_kind,
                       left(title, 100),
                       left(coalesce(summary, ''), 160),
                       category, published_at
                FROM issues
                WHERE content_kind = 'NEWS'
                ORDER BY first_seen_at DESC NULLS LAST
                LIMIT 5
                """
            )
        ).fetchall()
        print("=== NEWS rows ===")
        for row in rows:
            print(row)

        after = db.execute(
            text("SELECT count(*) FROM issues WHERE content_kind = 'NEWS'")
        ).scalar()
        print("news_after=", after)
        created = int(after or 0) - int(before or 0)
        print("news_created_this_run=", created)
        return 0 if created >= 1 else 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
