from abc import ABC, abstractmethod
from typing import Optional

from app.domain.models import RawItem, SourceType


class SourceProvider(ABC):
    """External data source adapter. Implementations must not be called from API handlers."""

    name: SourceType

    @abstractmethod
    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[RawItem]:
        raise NotImplementedError


class StubProvider(SourceProvider):
    """Placeholder until a real provider is wired."""

    def __init__(self, source_type: SourceType) -> None:
        self.name = source_type

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[RawItem]:
        return []
