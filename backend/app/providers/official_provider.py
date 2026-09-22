"""Official / regulatory sources. KR equities use OpenDART when keyed."""

from __future__ import annotations

from typing import Optional

from app.domain.models import RawItem, SourceType
from app.providers.base import SourceProvider, StubProvider
from app.providers.dart_provider import DartProvider


class OfficialProvider(SourceProvider):
    """
    Official disclosures adapter.
    - With DART_API_KEY: OpenDART filings for KRX symbols
    - Without key: empty (stub behavior)
    """

    name = SourceType.OFFICIAL

    def __init__(self) -> None:
        self._dart = DartProvider()

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
        symbol: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[RawItem]:
        if symbol and self._dart.api_key:
            return self._dart.fetch(
                query=query,
                since_id=since_id,
                limit=limit,
                symbol=symbol,
                name=name,
            )
        return StubProvider(SourceType.OFFICIAL).fetch(limit=limit)
