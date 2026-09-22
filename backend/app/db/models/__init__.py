from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.session import Base


def _uuid() -> str:
    return str(uuid4())


JSONType = JSON().with_variant(JSONB(), "postgresql")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    name_ko: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    exchange: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    market: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, default="US")
    kind: Mapped[str] = mapped_column(String(32), default="asset")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RawItem(Base):
    __tablename__ = "raw_items"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_raw_provider_external"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    content_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    processed: Mapped[int] = mapped_column(Integer, default=0)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    cluster_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="open")
    related_symbols: Mapped[list] = mapped_column(JSONType, default=list)
    related_sectors: Mapped[list] = mapped_column(JSONType, default=list)
    providers: Mapped[list] = mapped_column(JSONType, default=list)
    raw_item_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    signals: Mapped[list["Issue"]] = relationship(back_populates="event")
    raw_links: Mapped[list["EventRawItem"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventRawItem(Base):
    __tablename__ = "event_raw_items"
    __table_args__ = (
        UniqueConstraint("event_id", "raw_item_id", name="uq_event_raw_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    raw_item_id: Mapped[str] = mapped_column(ForeignKey("raw_items.id"), index=True)

    event: Mapped["Event"] = relationship(back_populates="raw_links")


class Issue(Base):
    """User-facing Issue card store (physical table renamed from signals)."""

    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("events.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    # Long-form Korean editorial for "컬럼 자세히 보기" (worker-generated).
    column_body: Mapped[str] = mapped_column(Text, default="")
    # Column byline (Finimize-style author credit).
    column_author_name: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    column_author_image_url: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    # Optional cover image — absolute http(s) URL or /media/issue-images/... path.
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    confirmed_facts: Mapped[list] = mapped_column(JSONType, default=list)
    key_points: Mapped[list] = mapped_column(JSONType, default=list)
    emphasis: Mapped[dict] = mapped_column(JSONType, default=dict)
    market_reaction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_mix: Mapped[list] = mapped_column(JSONType, default=list)
    content_type: Mapped[str] = mapped_column(String(32), default="REPORT", index=True)
    evidence_level: Mapped[str] = mapped_column(
        String(32), default="UNVERIFIED", index=True
    )
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    related_symbols: Mapped[list] = mapped_column(JSONType, default=list)
    related_sectors: Mapped[list] = mapped_column(JSONType, default=list)
    cluster_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    # Issue product fields.
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    topic: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    trend_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    is_trending: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_reply_peak: Mapped[int] = mapped_column(Integer, default=0)
    # MVP lifecycle: CANDIDATE | PUBLISHED | UPDATED | STALE | ARCHIVED
    # New Issues stay CANDIDATE/draft until admin publishes.
    lifecycle: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    # Orthogonal to lifecycle: NORMAL | RISING | TRENDING (transient current interest).
    trend_status: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, default="NORMAL"
    )
    # Set only when trend_status actually changes (hysteresis / grace).
    trend_status_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    participation_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    participation_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    participation_suitable: Mapped[bool] = mapped_column(Boolean, default=False)
    # Optional admin override for push re-engagement copy (empty → auto).
    push_title: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    push_body: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    # When False, consumer app hides source credit / source_count (admin still sees sources).
    show_sources: Mapped[bool] = mapped_column(Boolean, default=False)
    impression_count: Mapped[int] = mapped_column(Integer, default=0)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Earliest source published_at (what the UI should show as "N시간 전").
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    # Semantic content/evidence change — NOT bumped by impression/open counters.
    content_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )

    event: Mapped[Optional["Event"]] = relationship(back_populates="signals")
    sources: Mapped[list["SignalSource"]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )
    participation_options: Mapped[list["ParticipationOption"]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )
    participations: Mapped[list["Participation"]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )
    comments: Mapped[list["IssueComment"]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )
    follows: Mapped[list["IssueFollow"]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )
    views: Mapped[list["IssueView"]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )
    takes: Mapped[list["IssueTake"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )


# Backward-compatible ORM alias (same mapper / table `issues`).
Signal = Issue


class SignalSource(Base):
    __tablename__ = "signal_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), index=True)
    raw_item_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("raw_items.id"), nullable=True
    )
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    evidence_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # OFFICIAL | NEWS | SOCIAL | COMMUNITY | UNKNOWN — hint for LLM, not truth gate
    trust_tier: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    signal: Mapped["Issue"] = relationship(back_populates="sources")


class MetricSnapshot(Base):
    """Engagement snapshots for velocity / trend_status (not Issue create gates)."""

    __tablename__ = "metric_snapshots"
    __table_args__ = (
        Index("idx_metric_snapshots_signal_captured", "signal_id", "captured_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), index=True)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    retweet_count: Mapped[int] = mapped_column(Integer, default=0)
    quote_count: Mapped[int] = mapped_column(Integer, default=0)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ParticipationOption(Base):
    """Vote option for an Issue."""

    __tablename__ = "participation_options"
    __table_args__ = (
        Index("idx_participation_options_signal_order", "signal_id", "display_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), index=True)
    label: Mapped[str] = mapped_column(String(200))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    signal: Mapped["Issue"] = relationship(back_populates="participation_options")
    participations: Mapped[list["Participation"]] = relationship(
        back_populates="option"
    )


class Participation(Base):
    """One vote per user per Issue."""

    __tablename__ = "participations"
    __table_args__ = (
        UniqueConstraint("signal_id", "user_id", name="uq_participation_signal_user"),
        Index("idx_participations_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    option_id: Mapped[str] = mapped_column(
        ForeignKey("participation_options.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    signal: Mapped["Issue"] = relationship(back_populates="participations")
    option: Mapped["ParticipationOption"] = relationship(back_populates="participations")


class IssueComment(Base):
    """Flat comment on an Issue."""

    __tablename__ = "issue_comments"
    __table_args__ = (
        Index("idx_issue_comments_signal_created", "signal_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    signal: Mapped["Issue"] = relationship(back_populates="comments")


class IssueFollow(Base):
    """User subscription to an Issue (retention — not asset watchlist)."""

    __tablename__ = "issue_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "signal_id", name="uq_issue_follow_user_signal"),
        Index("idx_issue_follows_user_created", "user_id", "created_at"),
        Index("idx_issue_follows_signal", "signal_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    signal_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    signal: Mapped["Issue"] = relationship(back_populates="follows")


class IssueView(Base):
    """Per-user detail open cursor (Home impression must NOT update this)."""

    __tablename__ = "issue_views"
    __table_args__ = (
        UniqueConstraint("user_id", "signal_id", name="uq_issue_view_user_signal"),
        Index("idx_issue_views_user_seen", "user_id", "last_seen_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    signal_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    signal: Mapped["Issue"] = relationship(back_populates="views")


class IssueUserEvent(Base):
    """Append-only funnel events for retention analytics."""

    __tablename__ = "issue_user_events"
    __table_args__ = (
        Index("idx_issue_user_events_user_created", "user_id", "created_at"),
        Index("idx_issue_user_events_signal_created", "signal_id", "created_at"),
        Index("idx_issue_user_events_event_created", "event", "created_at"),
        Index("idx_issue_user_events_take_created", "take_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    # Nullable for user-scoped Contributor lifecycle events (apply/approved).
    signal_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("issues.id"), nullable=True, index=True
    )
    # Optional IssueTake id for Contributor funnel (Impact attribution = Future).
    take_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("issue_takes.id"), nullable=True, index=True
    )
    # Share funnel attribution (optional; no friend graph).
    share_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    ref_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    share_intent: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    event: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "asset_id", name="uq_watchlist_user_asset"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asset: Mapped["Asset"] = relationship()


class IngestCursor(Base):
    __tablename__ = "ingest_cursors"
    __table_args__ = (
        UniqueConstraint("provider", "cursor_key", name="uq_ingest_provider_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(32))
    cursor_key: Mapped[str] = mapped_column(String(255))
    cursor_value: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class MarketBrief(Base):
    __tablename__ = "market_briefs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    brief_date: Mapped[str] = mapped_column(String(10), index=True)
    transcript: Mapped[str] = mapped_column(Text)
    signal_ids: Mapped[list] = mapped_column(JSONType, default=list)
    audio_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    audio_status: Mapped[str] = mapped_column(String(32), default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MacroEvent(Base):
    """Shared macro calendar row (worker-synced). Not a news Signal."""

    __tablename__ = "macro_events"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_macro_provider_external"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(32), index=True, default="calendar")
    external_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(64), default="other", index=True)
    event_date: Mapped[date] = mapped_column(Date, index=True)
    event_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    region: Mapped[str] = mapped_column(String(16), default="US")
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    summary: Mapped[str] = mapped_column(Text, default="")
    source_agency: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(Base):
    """
    Device-first anonymous account (no email signup required).
    Client sends a stable device_id; server returns user.id for watchlist/brief.
    Pro state mirrors ssamdaeshin teachers.plan_type / plan_expire_at.
    Contributor permission is ONLY via contributor_status (not plan_type / status).
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(16), default="web")  # ios|android|web
    plan_type: Mapped[str] = mapped_column(String(16), default="FREE", index=True)
    plan_expire_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|withdrawn
    # Contributor card label only — not a full profile system.
    display_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # NONE|PENDING|APPROVED|REJECTED|SUSPENDED — orthogonal to User.status.
    contributor_status: Mapped[str] = mapped_column(
        String(32), default="NONE", index=True
    )
    contributor_approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    app_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    subscription_payments: Mapped[list["SubscriptionPayment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    contributor_applications: Mapped[list["ContributorApplication"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    issue_takes: Mapped[list["IssueTake"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )


class ContributorApplication(Base):
    """Application to become a Contributor (Gate 1). Status on this row is application-only."""

    __tablename__ = "contributor_applications"
    __table_args__ = (
        Index("idx_contributor_applications_user_created", "user_id", "created_at"),
        Index("idx_contributor_applications_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    motivation: Mapped[str] = mapped_column(Text, default="")
    interests: Mapped[str] = mapped_column(Text, default="")
    sample_text: Mapped[str] = mapped_column(Text, default="")
    # Application lifecycle: PENDING|APPROVED|REJECTED
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="contributor_applications")


class IssueTake(Base):
    """Contributor「깊이 있는 생각」— always bound to one Issue (not a standalone article)."""

    __tablename__ = "issue_takes"
    __table_args__ = (
        Index("idx_issue_takes_issue_status", "issue_id", "status"),
        Index("idx_issue_takes_author_created", "author_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text, default="")
    source_urls: Mapped[list] = mapped_column(JSONType, default=list)
    # draft|pending_review|published|rejected
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    reaction_count: Mapped[int] = mapped_column(Integer, default=0)
    # Reserved for Future Featured logic — no MVP behavior.
    featured_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )

    issue: Mapped["Issue"] = relationship(back_populates="takes")
    author: Mapped["User"] = relationship(back_populates="issue_takes")
    reactions: Mapped[list["IssueTakeReaction"]] = relationship(
        back_populates="take", cascade="all, delete-orphan"
    )


class IssueTakeReaction(Base):
    """Single「공감」per user per IssueTake — separate from IssueComment.like_count."""

    __tablename__ = "issue_take_reactions"
    __table_args__ = (
        UniqueConstraint("take_id", "user_id", name="uq_issue_take_reaction_user"),
        Index("idx_issue_take_reactions_take", "take_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    take_id: Mapped[str] = mapped_column(ForeignKey("issue_takes.id"), index=True)
    # Soft identity string (same pattern as comments/votes) — not Comment likes.
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    take: Mapped["IssueTake"] = relationship(back_populates="reactions")


class SubscriptionPayment(Base):
    """
    App Store / Play Store IAP history (ssamdaeshin-compatible shape).
    Entitlement = max(expires_at) among PAID rows for the user.
    """

    __tablename__ = "subscription_payments"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "transaction_id",
            name="uq_subscription_payments_platform_transaction",
        ),
        Index("idx_subscription_payments_user_expires", "user_id", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(String(128), index=True)
    platform: Mapped[str] = mapped_column(String(16), index=True)  # ios|android
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="KRW")
    payment_status: Mapped[str] = mapped_column(
        String(16), default="PAID", index=True
    )  # PAID|REFUNDED|FAILED
    payment_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    product_id: Mapped[str] = mapped_column(String(64), default="pro_monthly")
    purchase_token: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    original_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    environment: Mapped[str] = mapped_column(String(16), default="prod")  # sandbox|prod
    raw_receipt: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    last_verified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="subscription_payments")


class UsageEvent(Base):
    """Append-only cost proxy events (requests, tokens, characters)."""

    __tablename__ = "usage_events"
    __table_args__ = (
        Index("idx_usage_events_metric_created", "metric", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    metric: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[float] = mapped_column(Float, default=1.0)
    tags: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )


class UserPreference(Base):
    """Per-user app preferences (brief alarm, notifications)."""

    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    brief_alarm_time: Mapped[str] = mapped_column(String(5), default="07:00")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Seoul")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # OpenAI TTS gender preference: female | male (mapped to nova / onyx).
    tts_voice_gender: Mapped[str] = mapped_column(String(16), default="female")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class DeviceToken(Base):
    """FCM registration token (separate from users.device_id identity)."""

    __tablename__ = "device_tokens"
    __table_args__ = (
        UniqueConstraint("fcm_token", name="uq_device_tokens_fcm_token"),
        Index("idx_device_tokens_user_active", "user_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    fcm_token: Mapped[str] = mapped_column(String(512))
    platform: Mapped[str] = mapped_column(String(16), default="web")  # ios|android|web
    client_device_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    app_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PushNotification(Base):
    """Outbound push queue row (worker sends; API only enqueues via services)."""

    __tablename__ = "push_notifications"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_push_notifications_dedupe"),
        Index("idx_push_status_scheduled", "status", "scheduled_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)  # brief_ready|signal_new
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(
        String(16), default="pending", index=True
    )  # pending|sent|failed|cancelled
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PushNotificationLog(Base):
    """Per-device delivery attempt."""

    __tablename__ = "push_notification_logs"
    __table_args__ = (
        Index("idx_push_logs_notification", "notification_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    notification_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    fcm_token: Mapped[str] = mapped_column(String(512))
    platform: Mapped[str] = mapped_column(String(16), default="web")
    status: Mapped[str] = mapped_column(
        String(32)
    )  # success|failed|expired_token
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PushNotificationTemplate(Base):
    """Editable push copy per category. Placeholders: {title} {summary} {symbols} {brief_date} {signal_id}."""

    __tablename__ = "push_notification_templates"
    __table_args__ = (
        UniqueConstraint("category", "locale", name="uq_push_templates_category_locale"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    category: Mapped[str] = mapped_column(String(32), index=True)  # brief_ready|signal_new
    locale: Mapped[str] = mapped_column(String(16), default="ko")
    title_template: Mapped[str] = mapped_column(String(200))
    body_template: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
