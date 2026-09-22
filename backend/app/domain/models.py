from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    CONFIRMED_FACT = "confirmed_fact"
    MARKET_INTERPRETATION = "market_interpretation"
    OPINION = "opinion"
    RUMOR = "rumor"


class ContentType(str, Enum):
    FACT = "FACT"
    REPORT = "REPORT"
    MARKET_REACTION = "MARKET_REACTION"
    RUMOR = "RUMOR"
    OPINION = "OPINION"
    INVESTMENT_CALL = "INVESTMENT_CALL"
    PROMOTION = "PROMOTION"


class EvidenceLevel(str, Enum):
    CONFIRMED = "CONFIRMED"
    CORROBORATED = "CORROBORATED"
    UNVERIFIED = "UNVERIFIED"
    OPINION = "OPINION"


class AssetKind(str, Enum):
    MACRO = "macro"
    SECTOR = "sector"
    ASSET = "asset"
    TOPIC = "topic"


class SourceType(str, Enum):
    X = "x"
    REDDIT = "reddit"
    NEWS = "news"
    OFFICIAL = "official"
    SEC = "sec"
    IR = "ir"
    WEB = "web"
    CALENDAR = "calendar"


class MacroCalendarItem(BaseModel):
    """Normalized macro release from a CalendarProvider (worker-only)."""

    provider: str = "calendar"
    external_id: str
    title: str
    category: str
    event_date: date
    event_at: Optional[datetime] = None
    region: str = "US"
    importance: float = 0.5
    summary: str = ""
    source_agency: Optional[str] = None
    raw_payload: dict = Field(default_factory=dict)


class SymbolHit(BaseModel):
    """Reference-data hit from a symbol catalog provider (not a news RawItem)."""

    symbol: str
    name: str
    kind: str = AssetKind.ASSET.value
    exchange: Optional[str] = None
    name_ko: Optional[str] = None
    vendor: Optional[str] = None


class SignalStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    REJECTED = "rejected"


class RawItem(BaseModel):
    provider: SourceType
    external_id: str
    url: Optional[str] = None
    author: Optional[str] = None
    title: Optional[str] = None
    text: str
    language: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    raw_payload: dict = Field(default_factory=dict)


class MarketSignal(BaseModel):
    id: Optional[str] = None
    event_id: Optional[str] = None
    title: str
    summary: str
    why_it_matters: str
    # Long Korean editorial for detail "컬럼 자세히 보기".
    column_body: str = ""
    confirmed_facts: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    # UI emphasis hints from LLM: key_sentences / rise_numbers / fall_numbers
    emphasis: dict = Field(default_factory=dict)
    market_reaction: Optional[str] = None
    evidence_mix: list[EvidenceType] = Field(default_factory=list)
    content_type: str = "REPORT"
    evidence_level: str = "UNVERIFIED"
    importance: float = 0.5
    confidence: float = 0.5
    related_symbols: list[str] = Field(default_factory=list)
    related_sectors: list[str] = Field(default_factory=list)
    # Issue / participation (optional; finance Signals may leave these empty).
    category: Optional[str] = None
    topic: Optional[str] = None
    trend_score: float = 0.0
    is_trending: bool = False
    # Max reply_count seen on source posts in the cluster (X public_metrics).
    source_reply_peak: int = 0
    participation_suitable: bool = False
    participation_type: Optional[str] = None
    participation_question: Optional[str] = None
    participation_options: list[str] = Field(default_factory=list)
    status: SignalStatus = SignalStatus.DRAFT
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # Original source time (earliest published_at in cluster). Display this to users.
    published_at: Optional[datetime] = None
    source_urls: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
