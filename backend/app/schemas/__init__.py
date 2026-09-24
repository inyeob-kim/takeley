from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class SignalSourceOut(BaseModel):
    id: str
    url: Optional[str] = None
    provider: Optional[str] = None
    evidence_type: Optional[str] = None
    excerpt: Optional[str] = None
    title: Optional[str] = None

    model_config = {"from_attributes": True}


class SignalEmphasisOut(BaseModel):
    key_sentences: list[str] = Field(default_factory=list)
    rise_numbers: list[str] = Field(default_factory=list)
    fall_numbers: list[str] = Field(default_factory=list)


class SignalOut(BaseModel):
    id: str
    event_id: Optional[str] = None
    title: str
    summary: str
    why_it_matters: str
    confirmed_facts: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    market_reaction: Optional[str] = None
    evidence_mix: list[str] = Field(default_factory=list)
    content_type: str = "REPORT"
    evidence_level: str = "UNVERIFIED"
    importance: float
    confidence: float
    related_symbols: list[str] = Field(default_factory=list)
    related_sectors: list[str] = Field(default_factory=list)
    # symbol → Korean-first display label for UI chips
    symbol_labels: dict[str, str] = Field(default_factory=dict)
    status: str = "published"
    first_seen_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    sources: list[SignalSourceOut] = Field(default_factory=list)
    emphasis: SignalEmphasisOut = Field(default_factory=SignalEmphasisOut)

    model_config = {"from_attributes": True}


class SignalListOut(BaseModel):
    items: list[SignalOut]
    count: int
    quota: Optional[dict] = None


class AssetOut(BaseModel):
    id: str
    symbol: str
    name: str
    name_ko: Optional[str] = None
    display_name: str = ""
    exchange: Optional[str] = None
    market: Optional[str] = None
    kind: str

    model_config = {"from_attributes": True}


class WatchlistItemOut(BaseModel):
    id: str
    user_id: str
    asset: AssetOut
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchlistAddIn(BaseModel):
    symbol: str
    name: Optional[str] = None
    kind: str = "asset"


class WatchlistAddOut(BaseModel):
    item: WatchlistItemOut
    existing_signal_count: int = 0
    collecting: bool = False
    message: str = ""


class BriefOut(BaseModel):
    id: Optional[str] = None
    brief_date: str
    transcript: str
    signal_ids: list[str] = Field(default_factory=list)
    audio_url: Optional[str] = None
    audio_status: str = "none"
    created_at: Optional[datetime] = None


class UserSettingsOut(BaseModel):
    user_id: str
    brief_alarm_time: str
    timezone: str
    notifications_enabled: bool = True
    tts_voice_gender: str = "female"
    display_name: Optional[str] = None


class UserSettingsUpdateIn(BaseModel):
    brief_alarm_time: Optional[str] = None
    timezone: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    tts_voice_gender: Optional[str] = None
    display_name: Optional[str] = None


class MacroEventOut(BaseModel):
    id: str
    title: str
    category: str
    event_date: date
    event_at: Optional[datetime] = None
    region: str = "US"
    importance: float = 0.5
    summary: str = ""


class MacroEventListOut(BaseModel):
    items: list[MacroEventOut]
    count: int


class DeviceRegisterIn(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=128)
    platform: str = Field(default="web", pattern="^(ios|android|web)$")
    app_version: Optional[str] = Field(default=None, max_length=32)


class DeviceDeleteIn(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=128)
    user_id: str = Field(..., min_length=8, max_length=64)


class UserOut(BaseModel):
    id: str
    device_id: str
    platform: str
    plan_type: str = "FREE"
    plan_expire_at: Optional[datetime] = None
    is_pro: bool = False
    status: str = "active"
    created_at: datetime
    last_seen_at: Optional[datetime] = None


class DeviceRegisterOut(BaseModel):
    user: UserOut
    created: bool


class EntitlementOut(BaseModel):
    user_id: str
    pro: bool
    plan_type: str = "FREE"
    plan_expire_at: Optional[datetime] = None


class ProductIdsOut(BaseModel):
    ios_product_id: str
    android_product_id: str


class PushDeviceRegisterIn(BaseModel):
    fcm_token: str = Field(..., min_length=20, max_length=512)
    platform: str = Field(default="web", pattern="^(ios|android|web)$")
    user_id: Optional[str] = Field(default=None, max_length=64)
    device_id: Optional[str] = Field(default=None, min_length=8, max_length=128)
    client_device_id: Optional[str] = Field(default=None, max_length=128)
    app_version: Optional[str] = Field(default=None, max_length=32)


class PushDeviceRegisterOut(BaseModel):
    id: str
    user_id: str
    platform: str
    is_active: bool
    created: bool


class PushTemplateOut(BaseModel):
    id: str
    category: str
    locale: str
    title_template: str
    body_template: str
    is_active: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class PushTemplateUpdateIn(BaseModel):
    title_template: Optional[str] = Field(default=None, max_length=200)
    body_template: Optional[str] = None
    is_active: Optional[bool] = None


class PushTemplateListOut(BaseModel):
    items: list[PushTemplateOut]
    count: int


class SignalExplainIn(BaseModel):
    selection: str = Field(..., min_length=1, max_length=500)
    question: Optional[str] = Field(default=None, max_length=400)


class SignalExplainOut(BaseModel):
    answer: str
    model: str
    selection: str
    prompt_version: str = ""

class ParticipationOptionOut(BaseModel):
    id: str
    label: str
    display_order: int = 0
    count: int = 0

    model_config = {"from_attributes": True}


class IssueSourceOut(BaseModel):
    id: str
    url: Optional[str] = None
    provider: Optional[str] = None
    title: Optional[str] = None
    excerpt: Optional[str] = None
    author: Optional[str] = None


class IssueOut(BaseModel):
    id: str
    title: str
    summary: str
    why_it_matters: str = ""
    column_body: str = ""
    column_author_name: Optional[str] = None
    column_author_image_url: Optional[str] = None
    columnist_id: Optional[str] = None
    image_url: Optional[str] = None
    key_points: list[str] = Field(default_factory=list)
    category: Optional[str] = None
    topic: Optional[str] = None
    trend_score: float = 0.0
    is_trending: bool = False
    trend_status: str = "NORMAL"
    importance: float = 0.5
    confidence: float = 0.5
    content_type: str = "REPORT"
    evidence_level: str = "UNVERIFIED"
    related_symbols: list[str] = Field(default_factory=list)
    participation_suitable: bool = False
    participation_type: Optional[str] = None
    participation_question: Optional[str] = None
    show_sources: bool = False
    # Admin-only optional push overrides (empty → auto CTA).
    push_title: Optional[str] = None
    push_body: Optional[str] = None
    # Effective push copy that will be sent on publish (computed).
    push_preview_title: Optional[str] = None
    push_preview_body: Optional[str] = None
    push_kind: Optional[str] = None
    options: list[ParticipationOptionOut] = Field(default_factory=list)
    participation_count: int = 0
    my_option_id: Optional[str] = None
    source_count: int = 0
    sources: list[IssueSourceOut] = Field(default_factory=list)
    comment_count: int = 0
    impression_count: int = 0
    open_count: int = 0
    status: str = "published"
    published_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    content_updated_at: Optional[datetime] = None
    is_following: bool = False
    has_new_update: bool = False
    my_last_seen_at: Optional[datetime] = None


class IssueListOut(BaseModel):
    items: list[IssueOut]
    count: int


class IssueParticipateIn(BaseModel):
    option_id: str = Field(..., min_length=1)
    user_id: Optional[str] = None


class IssueParticipateOut(BaseModel):
    issue_id: str
    my_option_id: str
    participation_count: int
    options: list[ParticipationOptionOut]
    is_following: bool = False


class IssueCommentIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None


class IssueCommentOut(BaseModel):
    id: str
    issue_id: str
    user_id: str
    content: str
    like_count: int = 0
    created_at: datetime
    display_name: Optional[str] = None
    issue_title: str = ""


class IssueCommentListOut(BaseModel):
    items: list[IssueCommentOut]
    count: int


class IssueEventIn(BaseModel):
    event: str = Field(
        ...,
        pattern=(
            "^(impression|open|update_seen|follow|unfollow|vote|comment|"
            "my_issue_open|share_clicked|share_completed|share_cancelled|"
            "share_link_copied|shared_link_opened|store_click|push_opened)$"
        ),
    )
    user_id: Optional[str] = None
    share_id: Optional[str] = Field(default=None, max_length=36)
    ref_user_id: Optional[str] = Field(default=None, max_length=64)
    share_intent: Optional[str] = Field(default=None, max_length=16)


class IssueEventOut(BaseModel):
    ok: bool = True
    impression_count: int = 0
    open_count: int = 0


class IssueFollowOut(BaseModel):
    issue_id: str
    is_following: bool
    has_new_update: bool = False


class IssueViewOut(BaseModel):
    issue_id: str
    my_last_seen_at: datetime
    has_new_update: bool = False


class ContributorStatsOut(BaseModel):
    takes_count: int = 0
    total_views: int = 0
    total_reactions: int = 0


class MyDeepThoughtOut(BaseModel):
    id: str
    issue_id: str
    issue_title: str = ""
    title: str
    status: str
    view_count: int = 0
    reaction_count: int = 0
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class MyActivityOut(BaseModel):
    participations: list[IssueOut] = Field(default_factory=list)
    followed: list[IssueOut] = Field(default_factory=list)
    comments: list[IssueCommentOut] = Field(default_factory=list)
    # Additive Contributor fields — null/empty unless contributor_status == APPROVED.
    contributor_stats: Optional[ContributorStatsOut] = None
    my_deep_thoughts: list[MyDeepThoughtOut] = Field(default_factory=list)


class ContributorApplicationIn(BaseModel):
    motivation: str = Field(..., min_length=1, max_length=500)
    interests: str = Field(..., min_length=1, max_length=200)
    sample_text: str = Field(default="", max_length=2000)
    user_id: Optional[str] = None


class ContributorApplicationOut(BaseModel):
    id: str
    user_id: str
    motivation: str
    interests: str
    sample_text: str
    status: str
    admin_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime] = None
    contributor_status: str


class ContributorMeOut(BaseModel):
    user_id: str
    contributor_status: str
    display_name: Optional[str] = None
    contributor_approved_at: Optional[datetime] = None
    application: Optional[ContributorApplicationOut] = None


class ContributorApplicationListOut(BaseModel):
    items: list[ContributorApplicationOut]
    count: int


class AdminContributorRejectIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class IssueTakeIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    body: str = Field(..., min_length=1, max_length=12000)
    source_urls: list[str] = Field(default_factory=list, max_length=10)
    user_id: Optional[str] = None
    # If provided, must match path issue_id.
    issue_id: Optional[str] = None


class IssueTakeUpdateIn(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    body: Optional[str] = Field(default=None, min_length=1, max_length=12000)
    source_urls: Optional[list[str]] = Field(default=None, max_length=10)
    user_id: Optional[str] = None


class IssueTakeOut(BaseModel):
    id: str
    issue_id: str
    author_id: str
    display_name: Optional[str] = None
    title: str
    body: str
    source_urls: list[str] = Field(default_factory=list)
    status: str
    view_count: int = 0
    reaction_count: int = 0
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    # Author/admin only — omitted/null for public list of published takes.
    admin_note: Optional[str] = None


class IssueTakePublicOut(BaseModel):
    id: str
    issue_id: str
    author_id: str
    display_name: Optional[str] = None
    title: str
    body: str
    source_urls: list[str] = Field(default_factory=list)
    status: str
    view_count: int = 0
    reaction_count: int = 0
    published_at: Optional[datetime] = None
    created_at: datetime


class IssueTakeListOut(BaseModel):
    items: list[IssueTakePublicOut]
    count: int


class IssueTakeReactionOut(BaseModel):
    ok: bool = True
    take_id: str
    reaction_count: int
    already_reacted: bool = False


class AdminTakeRejectIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class AdminTakeListOut(BaseModel):
    items: list[IssueTakeOut]
    count: int


class ColumnistOut(BaseModel):
    id: str
    display_name: str
    headline: str = ""
    bio: str = ""
    specialties: list[str] = Field(default_factory=list)
    contact_email: Optional[str] = None
    show_email: bool = False
    profile_public: bool = True
    image_url: Optional[str] = None
    status: str = "active"
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ColumnistListOut(BaseModel):
    items: list[ColumnistOut]
    count: int


class ColumnistIssueCardOut(BaseModel):
    id: str
    title: str
    summary: str
    category: Optional[str] = None
    image_url: Optional[str] = None
    published_at: Optional[datetime] = None
    content_updated_at: Optional[datetime] = None


class ColumnistProfileOut(BaseModel):
    id: str
    display_name: str
    headline: str = ""
    bio: str = ""
    specialties: list[str] = Field(default_factory=list)
    email: Optional[str] = None
    image_url: Optional[str] = None
    status: str = "active"
    issue_count: int = 0
    issues: list[ColumnistIssueCardOut] = Field(default_factory=list)


class ColumnistIssueListOut(BaseModel):
    items: list[ColumnistIssueCardOut]
    count: int
    offset: int = 0
    limit: int = 10


class AdminColumnistIn(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=128)
    headline: str = Field(default="", max_length=160)
    bio: str = Field(default="", max_length=8000)
    specialties: list[str] = Field(default_factory=list, max_length=12)
    contact_email: Optional[str] = Field(default=None, max_length=254)
    show_email: bool = False
    profile_public: bool = True
    image_url: Optional[str] = None
    status: str = Field(default="active", pattern="^(active|archived)$")
    sort_order: Optional[int] = None


class AdminColumnistPatchIn(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    headline: Optional[str] = Field(default=None, max_length=160)
    bio: Optional[str] = Field(default=None, max_length=8000)
    specialties: Optional[list[str]] = Field(default=None, max_length=12)
    contact_email: Optional[str] = Field(default=None, max_length=254)
    show_email: Optional[bool] = None
    profile_public: Optional[bool] = None
    image_url: Optional[str] = None
    clear_image: bool = False
    status: Optional[str] = Field(default=None, pattern="^(active|archived)$")
    sort_order: Optional[int] = None
