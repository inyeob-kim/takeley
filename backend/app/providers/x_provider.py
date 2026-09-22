"""X (Twitter) source provider — adapted from legacy fetcher patterns."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.core.config import get_settings
from app.domain.models import RawItem, SourceType
from app.providers.base import SourceProvider

logger = logging.getLogger(__name__)


class XProvider(SourceProvider):
    name = SourceType.X

    def __init__(
        self,
        bearer_token: Optional[str] = None,
        accounts: tuple[str, ...] | None = None,
    ) -> None:
        settings = get_settings()
        self.bearer_token = bearer_token or settings.twitter_bearer_token
        self.accounts = accounts if accounts is not None else settings.tracked_x_accounts()
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.bearer_token:
            logger.warning("TWITTER_BEARER_TOKEN not set; XProvider returns demo items")
            return None
        import tweepy

        self._client = tweepy.Client(bearer_token=self.bearer_token)
        return self._client

    def resolve_user_id(
        self,
        username: str,
        *,
        cached_user_id: Optional[str] = None,
    ) -> Optional[str]:
        """Map username → numeric id. Prefer cache to avoid get_user each cycle."""
        if cached_user_id and str(cached_user_id).isdigit():
            return str(cached_user_id)
        client = self._get_client()
        if client is None:
            return None
        try:
            user = client.get_user(username=username)
            if not user or not user.data:
                return None
            return str(user.data.id)
        except Exception:
            logger.exception("XProvider get_user failed for @%s", username)
            return None

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[RawItem]:
        """Fetch across accounts using one since_id (prefer fetch_account)."""
        client = self._get_client()
        if client is None:
            return self._demo_items(query=query)

        items: list[RawItem] = []
        for username in self.accounts:
            items.extend(
                self.fetch_account(
                    username=username,
                    since_id=since_id,
                    limit=max(5, limit // max(len(self.accounts), 1)),
                )
            )
        return items[:limit]

    def fetch_account(
        self,
        *,
        username: str,
        since_id: Optional[str] = None,
        limit: int = 10,
        cached_user_id: Optional[str] = None,
    ) -> list[RawItem]:
        """Fetch recent timeline posts. Caller applies universe relevance."""
        client = self._get_client()
        if client is None:
            # Demo mode: only emit once via fetch(), not per account.
            return []

        items: list[RawItem] = []
        try:
            user_id = self.resolve_user_id(username, cached_user_id=cached_user_id)
            if not user_id:
                return []
            kwargs = {
                "id": user_id,
                "max_results": min(max(limit, 5), 100),
                "tweet_fields": ["created_at", "lang", "text"],
                # Match search ingest: skip pure retweets (quotes/replies still allowed).
                "exclude": ["retweets"],
            }
            if since_id and since_id.isdigit():
                kwargs["since_id"] = since_id
            logger.info(
                "x_api call=get_users_tweets account=@%s max=%s since_id=%s",
                username,
                kwargs["max_results"],
                since_id or "-",
            )
            resp = client.get_users_tweets(**kwargs)
            if not resp or not resp.data:
                logger.info(
                    "x_api done=get_users_tweets account=@%s results=0",
                    username,
                )
                return []
            for tweet in resp.data:
                text = tweet.text or ""
                items.append(
                    RawItem(
                        provider=SourceType.X,
                        external_id=str(tweet.id),
                        url=f"https://x.com/{username}/status/{tweet.id}",
                        author=username,
                        text=text,
                        language=getattr(tweet, "lang", None),
                        published_at=getattr(tweet, "created_at", None),
                        fetched_at=datetime.utcnow(),
                        raw_payload={
                            "username": username,
                            "user_id": user_id,
                        },
                    )
                )
            logger.info(
                "x_api done=get_users_tweets account=@%s results=%s",
                username,
                len(items),
            )
            _log_fetch_samples(items, context=f"x.account:@{username}")
        except Exception:
            logger.exception("XProvider failed for @%s", username)
        return items

    def fetch_search(
        self,
        *,
        query: str,
        since_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[RawItem]:
        """Recent search by keyword query (no account map required)."""
        client = self._get_client()
        if client is None:
            return []

        items: list[RawItem] = []
        try:
            kwargs = {
                "query": query,
                "max_results": min(max(limit, 10), 100),
                "tweet_fields": [
                    "created_at",
                    "lang",
                    "text",
                    "author_id",
                    "public_metrics",
                ],
                "sort_order": "relevancy",
            }
            if since_id and since_id.isdigit():
                kwargs["since_id"] = since_id
            logger.info(
                "x_api call=search_recent_tweets max=%s since_id=%s query=%s",
                kwargs["max_results"],
                since_id or "-",
                query[:160],
            )
            resp = client.search_recent_tweets(**kwargs)
            if not resp or not resp.data:
                logger.info(
                    "x_api done=search_recent_tweets results=0 query=%s",
                    query[:120],
                )
                return []
            for tweet in resp.data:
                text = tweet.text or ""
                author = str(getattr(tweet, "author_id", "") or "unknown")
                metrics = getattr(tweet, "public_metrics", None) or {}
                if hasattr(metrics, "items"):
                    metrics = dict(metrics)
                elif not isinstance(metrics, dict):
                    metrics = {}
                items.append(
                    RawItem(
                        provider=SourceType.X,
                        external_id=str(tweet.id),
                        url=f"https://x.com/i/web/status/{tweet.id}",
                        author=author,
                        text=text,
                        language=getattr(tweet, "lang", None),
                        published_at=getattr(tweet, "created_at", None),
                        fetched_at=datetime.utcnow(),
                        raw_payload={
                            "search_query": query,
                            "author_id": author,
                            "public_metrics": metrics,
                        },
                    )
                )
            logger.info(
                "x_api done=search_recent_tweets results=%s query=%s",
                len(items),
                query[:120],
            )
            _log_fetch_samples(items, context=f"x.search:{query[:40]}")
        except Exception:
            logger.exception("XProvider search failed query=%s", query[:80])
        return items

    def _demo_items(self, query: Optional[str] = None) -> list[RawItem]:
        now = datetime.utcnow()
        samples = [
            (
                "demo-x-1",
                "Fed officials signal caution on the next rate move as inflation data stays sticky.",
                "DeItaone",
            ),
            (
                "demo-x-2",
                "Oil rises after OPEC supply chatter; traders watch crude inventories this week.",
                "StockMKTNewz",
            ),
            (
                "demo-x-3",
                "Apple supplier update and US mega-cap futures mixed into the open.",
                "FirstSquawk",
            ),
        ]
        return [
            RawItem(
                provider=SourceType.X,
                external_id=eid,
                url=f"https://x.com/{author}/status/{eid}",
                author=author,
                text=text,
                language="en",
                published_at=now,
                fetched_at=now,
                raw_payload={"demo": True, "query": query, "username": author},
            )
            for eid, text, author in samples
        ]


def _log_fetch_samples(items: list, *, context: str, limit: int = 3) -> None:
    """Short INFO previews so fetch contents are visible without DEBUG noise."""
    from app.core.logging import preview_text

    for idx, item in enumerate(items[:limit], start=1):
        metrics = (item.raw_payload or {}).get("public_metrics") or {}
        logger.info(
            "%s sample#%s id=%s likes=%s replies=%s text=%s",
            context,
            idx,
            item.external_id,
            metrics.get("like_count", "-"),
            metrics.get("reply_count", "-"),
            preview_text(item.text, 90),
        )
