"""Backfill NEWS column_body via news_card_v5 (+ optional OG image_url)."""

from __future__ import annotations

import json
import logging
import os
import sys

os.environ.setdefault("NEWS_PIPELINE_ENABLED", "true")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.pipeline.news_generate import generate_news_card
from app.providers.article_fetch import fetch_article_body

get_settings.cache_clear()


def main() -> int:
    limit = int(os.environ.get("NEWS_BACKFILL_LIMIT", "8"))
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT i.id::text,
                       i.title,
                       i.image_url,
                       length(coalesce(i.column_body, '')) AS body_len,
                       ss.provider,
                       ss.url,
                       r.title AS raw_title,
                       r.text AS raw_text,
                       r.raw_payload
                FROM issues i
                LEFT JOIN LATERAL (
                  SELECT provider, url, raw_item_id
                  FROM signal_sources
                  WHERE signal_id = i.id
                  ORDER BY id
                  LIMIT 1
                ) ss ON true
                LEFT JOIN raw_items r ON r.id = ss.raw_item_id
                WHERE i.content_kind = 'NEWS'
                  AND i.status IN ('published', 'draft')
                ORDER BY i.first_seen_at DESC NULLS LAST
                LIMIT :lim
                """
            ),
            {"lim": limit},
        ).mappings().all()

        updated = 0
        for row in rows:
            raw_text = (row["raw_text"] or "").strip()
            if len(raw_text) < 80:
                print("skip short raw", row["id"], (row["title"] or "")[:40])
                continue
            card = generate_news_card(
                text=raw_text,
                provider=row["provider"] or "news",
                source_title=row["raw_title"] or row["title"],
                source_url=row["url"],
            )
            if not card.ok or len(card.body) < 80:
                print("skip generate", row["id"], card.reason, len(card.body))
                continue

            cover = (row["image_url"] or "").strip() or None
            payload = row["raw_payload"] if isinstance(row["raw_payload"], dict) else {}
            if not cover and isinstance(payload, dict):
                cover = (payload.get("image_url") or "").strip() or None
            if not cover and row["url"]:
                article = fetch_article_body(row["url"], min_chars=40)
                if article.image_url:
                    cover = article.image_url
                    print("fetched image", row["id"], cover[:80])

            db.execute(
                text(
                    """
                    UPDATE issues
                    SET title = :title,
                        summary = :summary,
                        column_body = :body,
                        key_points = CAST(:points AS jsonb),
                        category = COALESCE(:category, category),
                        image_url = COALESCE(:image_url, image_url),
                        content_updated_at = NOW(),
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "title": card.title,
                    "summary": card.summary,
                    "body": card.body,
                    "points": json.dumps(card.key_points, ensure_ascii=False),
                    "category": card.category,
                    "image_url": cover,
                },
            )
            updated += 1
            print(
                "updated",
                row["id"],
                "body_chars=",
                len(card.body),
                "has_image=",
                bool(cover),
                "title=",
                card.title[:50],
            )
        db.commit()
        print("updated_count=", updated)
        return 0 if updated else 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
