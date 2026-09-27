"""Reddit listings via application-only OAuth. Public .json is blocked."""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import get_settings
from app.domain.models import RawItem, SourceType
from app.providers.base import SourceProvider
from app.providers.http_headers import takeley_headers

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_LISTING_URL = "https://oauth.reddit.com/r/{subreddit}/hot"


class RedditAuthError(RuntimeError):
    pass


class RedditProvider(SourceProvider):
    name = SourceType.REDDIT

    def __init__(self, *, timeout_seconds: float = 12.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._token: str | None = None
        self._token_expires_at = 0.0

    def configured(self) -> bool:
        settings = get_settings()
        return bool(settings.reddit_client_id.strip() and settings.reddit_client_secret.strip())

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[RawItem]:
        # Leftover ticker ingest still calls fetch(). Discovery uses fetch_subreddit.
        if not (query or "").strip():
            return []
        return self.fetch_subreddit(query, limit=limit)

    def fetch_subreddit(self, subreddit: str, *, limit: int = 15) -> list[RawItem]:
        name = (subreddit or "").strip().lstrip("r/")
        if not name:
            return []
        token = self._access_token()
        headers = takeley_headers()
        headers["Authorization"] = f"Bearer {token}"
        url = _LISTING_URL.format(subreddit=name)
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(
                url,
                params={"limit": min(max(limit, 1), 50), "raw_json": 1},
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        return parse_reddit_listing(payload, subreddit=name)

    def _access_token(self) -> str:
        now = time.monotonic()
        if self._token and now < self._token_expires_at:
            return self._token
        settings = get_settings()
        client_id = settings.reddit_client_id.strip()
        secret = settings.reddit_client_secret.strip()
        if not client_id or not secret:
            raise RedditAuthError("reddit oauth credentials missing")
        basic = base64.b64encode(f"{client_id}:{secret}".encode("utf-8")).decode("ascii")
        headers = takeley_headers()
        headers["Authorization"] = f"Basic {basic}"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.post(
                _TOKEN_URL,
                headers=headers,
                data={"grant_type": "client_credentials"},
            )
            response.raise_for_status()
            payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RedditAuthError("reddit oauth token empty")
        ttl = max(60, int(payload.get("expires_in") or 3600) - 60)
        self._token = token
        self._token_expires_at = now + ttl
        return token


def parse_reddit_listing(payload: dict, *, subreddit: str) -> list[RawItem]:
    children = ((payload or {}).get("data") or {}).get("children") or []
    items: list[RawItem] = []
    for child in children:
        data = child.get("data") if isinstance(child, dict) else None
        if not isinstance(data, dict):
            continue
        post_id = str(data.get("id") or "").strip()
        title = str(data.get("title") or "").strip()
        if not post_id or not title:
            continue
        body = str(data.get("selftext") or "").strip()
        permalink = str(data.get("permalink") or "").strip()
        url = str(data.get("url") or "").strip()
        page = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else url
        created = data.get("created_utc")
        published_at = None
        if isinstance(created, (int, float)):
            published_at = datetime.fromtimestamp(float(created), tz=timezone.utc).replace(
                tzinfo=None
            )
        text = f"{title}. {body}".strip(" .")
        comments = int(data.get("num_comments") or 0)
        items.append(
            RawItem(
                provider=SourceType.REDDIT,
                external_id=post_id,
                url=page or url or None,
                author=str(data.get("author") or "reddit"),
                title=title,
                text=text,
                language="",
                published_at=published_at,
                fetched_at=datetime.utcnow(),
                raw_payload={
                    "source": "reddit",
                    "subreddit": str(data.get("subreddit") or subreddit),
                    "canonical_url": page or url,
                    "metrics": {
                        "like_count": int(data.get("ups") or 0),
                        "reply_count": comments,
                    },
                },
            )
        )
    return items
