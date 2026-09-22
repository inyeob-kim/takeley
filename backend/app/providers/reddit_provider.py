from app.providers.base import StubProvider
from app.domain.models import SourceType


class RedditProvider(StubProvider):
    def __init__(self) -> None:
        super().__init__(SourceType.REDDIT)
