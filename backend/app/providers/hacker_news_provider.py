"""Hacker News Firebase API → RawItem. Stories only; no comment crawl."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx

from app.domain.models import RawItem, SourceType
from app.providers.base import SourceProvider
from app.providers.http_headers import takeley_headers

_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"


class HackerNewsProvider(SourceProvider):
    name = SourceType.HACKER_NEWS

    def __init__(self, *, timeout_seconds: float = 12.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[RawItem]:
        return self.fetch_top(limit=limit)

    def fetch_top(self, *, limit: int = 30) -> list[RawItem]:
        cap = min(max(limit, 1), 50)
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            top = client.get(_TOP_URL, headers=takeley_headers())
            top.raise_for_status()
            ids = top.json()
            if not isinstance(ids, list):
                return []
            items: list[RawItem] = []
            for item_id in ids[:cap]:
                try:
                    resp = client.get(
                        _ITEM_URL.format(item_id=int(item_id)),
                        headers=takeley_headers(),
                    )
                    resp.raise_for_status()
                    parsed = parse_hn_item(resp.json())
                    if parsed:
                        items.append(parsed)
                except Exception:
                    continue
        return items


def parse_hn_item(payload: dict | None) -> RawItem | None:
    data = payload if isinstance(payload, dict) else None
    if not data or data.get("dead") or data.get("deleted"):
        return None
    item_id = data.get("id")
    title = str(data.get("title") or "").strip()
    if item_id is None or not title:
        return None
    body = str(data.get("text") or "").strip()
    url = str(data.get("url") or "").strip()
    page = url or f"https://news.ycombinator.com/item?id={item_id}"
    published_at = None
    if isinstance(data.get("time"), (int, float)):
        published_at = datetime.fromtimestamp(float(data["time"]), tz=timezone.utc).replace(
            tzinfo=None
        )
    text = f"{title}. {body}".strip(" .")
    return RawItem(
        provider=SourceType.HACKER_NEWS,
        external_id=str(item_id),
        url=page,
        author=str(data.get("by") or "hn"),
        title=title,
        text=text,
        published_at=published_at,
        fetched_at=datetime.utcnow(),
        raw_payload={
            "source": "hacker_news",
            "hn_id": item_id,
            "canonical_url": page,
            "metrics": {
                "like_count": int(data.get("score") or 0),
                "reply_count": int(data.get("descendants") or 0),
            },
        },
    )
