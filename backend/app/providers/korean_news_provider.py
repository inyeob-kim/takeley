"""Korean equity news via Google News RSS (hl=ko). Reuses NewsProvider body enrich."""

from __future__ import annotations

from typing import Optional

from app.domain.models import RawItem
from app.providers.news_provider import NewsProvider


class KoreanNewsProvider(NewsProvider):
    """KR locale Google News search + article body gate (same as EN news)."""

    def __init__(self) -> None:
        # Base URL only used to detect google news rewrite in parent.fetch.
        super().__init__(
            rss_url="https://news.google.com/rss/search?q=삼성전자&hl=ko&gl=KR&ceid=KR:ko",
            locale="ko",
        )

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
        symbol: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[RawItem]:
        return super().fetch(
            query=query,
            since_id=since_id,
            limit=limit,
            symbol=symbol,
            name=name,
        )
