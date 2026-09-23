from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    debug: bool = False
    # When true, clamp heavy wake + source fetch intervals to test_ingest_interval_seconds.
    # Local retest only — keep false in production.
    test_fast_ingest: bool = False
    test_ingest_interval_seconds: int = 60
    # Soft daily Issue publish pool (0 → use daily_signal_cap).
    daily_issue_soft_cap: int = 0
    # Embeddings assist Match shortlist only (LLM still decides same-Issue).
    issue_embedding_enabled: bool = True
    issue_embedding_model: str = "text-embedding-3-small"
    # Second LLM quality judge after card structuring.
    issue_llm_quality_judge_enabled: bool = True
    # Dynamic X queries from recent topics (extra search budget).
    issue_dynamic_query_enabled: bool = True
    issue_dynamic_query_budget: int = 2
    # When true, skip ticker X search / DART / Reddit stub in default heavy ingest.
    issue_ingest_focus: bool = True
    # Max LLM Understanding calls per process cycle (cost cap).
    issue_llm_understand_budget_per_cycle: int = 12
    # Max recent Issues shown to Match LLM as shortlist.
    issue_llm_match_shortlist: int = 8
    # Public columnist profile: first page + load-more page size.
    columnist_issue_page_size: int = 10
    columnist_issue_page_max: int = 40
    # Explicit override: DEBUG | INFO | WARNING | ERROR. Empty → derive from env/debug.
    log_level: str = ""
    # Admin review portal — header X-Admin-Key. Empty → admin routes disabled.
    admin_api_key: str = ""
    # Local default is SQLite so the API/worker run without Docker.
    # For local SQLite fallback: sqlite:///./takeley.db
    # Docker Compose Postgres (default for launch):
    database_url: str = "postgresql+psycopg://takeley:takeley@localhost:5432/takeley"
    openai_api_key: str = ""
    # Chat completions model for analyze / select / brief synthesize.
    openai_model: str = "gpt-4o-mini"
    twitter_bearer_token: str = ""
    mvp_asset_symbol: str = "TSLA"
    mvp_asset_name: str = "Tesla"
    mvp_asset_name_ko: str = "테슬라"
    # Shared US monitor set. Manage ONLY via MONITOR_SET_SYMBOLS in .env
    # (comma-separated tickers). Empty = MVP seed + watchlist only. Restart worker after edits.
    monitor_set_symbols: str = ""
    # Macro / geopolitics / commodity keep terms (comma-separated). Empty → built-in defaults.
    macro_theme_keywords: str = ""
    # When a macro-only item has no ticker, tag these index symbols for ranking/brief.
    macro_index_symbols: str = "SPY,QQQ"
    # Max distinct X symbol-search queries per ingest cycle (budget cap).
    x_search_query_budget: int = 8
    ingest_interval_seconds: int = 1800
    # Brief/TTS poll loop (separate from heavy ingest cycle). Target: within ~1 min of alarm.
    brief_poll_interval_seconds: int = 60
    default_user_id: str = "demo-user"
    # Home feed: watchlist hits get this many seconds of "newer" bump (not a full re-rank).
    home_watchlist_boost_seconds: int = 5400
    # Publish quota (soft pool + guarantees + absolute ceiling).
    # DAILY_SIGNAL_CAP = soft daily pool for NORMAL publishes (not a hard block).
    daily_signal_cap: int = 10
    # Guarantee slots per ticker when soft pool is empty (still under hard ceiling).
    per_symbol_daily_min: int = 2
    # Absolute published-today max a bootstrap focus symbol may reach via bypass.
    bootstrap_per_symbol_max: int = 3
    # Absolute max published Signals per UTC day (all paths). Stops watchlist explosion.
    daily_signal_hard_ceiling: int = 30
    # Optional HIGH escape using existing importance (set >1.0 to disable).
    priority_importance_threshold: float = 0.85
    min_signal_importance: float = 0.4
    min_signal_confidence: float = 0.3
    # Neutral Google News base; per-symbol ingest rebuilds q= when URL is news.google.com.
    news_rss_url: str = (
        "https://news.google.com/rss/search?q=US+stocks&hl=en-US&gl=US&ceid=US:en"
    )
    # Personalized brief (worker-only LLM select + script)
    brief_candidate_limit: int = 24
    brief_slot_count: int = 6
    personal_select_prompt_version: str = "personal_select_v4"
    brief_synthesize_prompt_version: str = "brief_synthesize_v3"
    signal_analysis_prompt_version: str = "issue_card_v3"
    # Comma-separated X usernames for account-timeline ingest (no @). Prefer US wires.
    x_track_accounts: str = "DeItaone,StockMKTNewz,FirstSquawk"
    # Issue industries for trending topic ingest (comma-separated keys).
    # Keys: politics,economy,finance,tech,ai,society,world,culture,sports,entertainment
    # Each enabled industry expands to korea+global discovery lanes (budget-capped RR).
    issue_industries: str = (
        "politics,economy,finance,tech,ai,society,world,culture,sports,entertainment"
    )
    # X recent-search by industry topic (debate / trending issues). Complements ticker search.
    issue_x_topic_enabled: bool = True
    x_topic_search_interval_seconds: int = 1800
    # Max industry×lane discovery queries per topic cycle (round-robin over ≤20 lanes).
    x_topic_query_budget: int = 8
    # Topic posts must clear this engagement score (likes + 3*replies + 2*rts + 2.5*quotes).
    issue_min_engagement_score: float = 15.0
    # Minimum X reply_count (comments) before a post can be kept / marked trending.
    issue_min_reply_count: int = 5
    # External velocity thresholds (replies/hour, engagement/hour).
    issue_rising_reply_velocity: float = 5.0
    issue_rising_engagement_velocity: float = 20.0
    issue_trending_reply_velocity: float = 20.0
    issue_trending_engagement_velocity: float = 80.0
    # TAKELEY internal interest gate (unique openers / follows / votes).
    # External fame alone must not yield RISING/TRENDING without this.
    issue_trend_min_unique_opens: int = 2
    issue_trend_min_follows: int = 1
    issue_trend_min_participations: int = 1
    # Recent-interest window for Trend internal + AI/snapshot freshness (hours).
    # IssueFollow rows are never expired; only Trend counting uses this window.
    issue_trend_internal_window_hours: float = 24.0
    # Downgrade grace (minutes). Default ≈ 2× ingest_interval_seconds; config only.
    issue_trend_downgrade_grace_minutes: float = 60.0
    # Keep at most this many hot posts per industry query after heat filter.
    issue_topic_keep_per_query: int = 8
    # Topic-sourced clusters: participation is optional (read-only Issues OK).
    # Kept for env compat; no longer hard-rejects publish.
    issue_topic_require_participation: bool = False
    # Per-source ingest intervals (worker still wakes on ingest_interval_seconds).
    x_accounts_interval_seconds: int = 3600
    x_search_interval_seconds: int = 1800
    rss_interval_seconds: int = 3600
    # After RSS, fetch publisher HTML and extract article body (required for factual analyze).
    news_fetch_body: bool = True
    news_body_timeout_seconds: float = 12.0
    news_body_max_chars: int = 6000
    news_body_min_chars: int = 280
    # RSS over-fetch multipliers (paywalls drop many candidates).
    news_rss_parse_multiplier: int = 5
    news_body_scan_multiplier: int = 4
    # Local-only: inject demo news when RSS itself fails. Never used for body-less real items.
    news_demo_fallback: bool = False
    # Worker TTS for listen-able briefs
    tts_enabled: bool = True
    tts_model: str = "tts-1"
    tts_voice: str = "nova"
    brief_audio_dir: str = "./storage/briefs"
    # Admin-uploaded Issue cover images (served at /media/issue-images).
    issue_image_dir: str = "./storage/issue_images"
    issue_image_max_bytes: int = 5_000_000
# Comma-separated origins for admin / local tools (Vite).
    cors_origins: str = "http://localhost:5174,http://127.0.0.1:5174"
    # Optional legacy web SPA origin (unused by share landing; kept for compat).
    public_web_origin: str = ""
    # Origin used in og:url / absolute share links (usually the API host).
    public_share_origin: str = "http://127.0.0.1:8000"
    # Optional store URLs for share-landing “앱이 없다면” (empty → web hint).
    public_android_store_url: str = ""
    public_ios_store_url: str = ""
    # Symbol catalog (vendor lookup + DB cache). Prefer Finnhub when keyed.
    finnhub_api_key: str = ""
    # OpenDART (KR disclosures). Empty → KR official ingest skipped.
    dart_api_key: str = ""
    dart_lookback_days: int = 14
    dart_interval_seconds: int = 3600
    dart_corp_code_cache_path: str = "./storage/dart_corp_codes.json"
    # Korean Google News RSS for KRX symbols. Seohak MVP default OFF (US sources only).
    kr_news_enabled: bool = False
    kr_news_interval_seconds: int = 3600
    symbol_yahoo_enabled: bool = True
    symbol_vendor_timeout_seconds: float = 5.0
    asset_search_limit: int = 20
    # Macro calendar (worker sync → DB; API reads DB only)
    calendar_api_url: str = "https://xoomar.com/api/markets/calendar"
    calendar_sync_interval_seconds: int = 86400
    calendar_lookback_days: int = 7
    calendar_lookahead_days: int = 60
    calendar_importance: str = "high"
    calendar_timeout_seconds: float = 15.0
    calendar_seed_fallback: bool = True
    # IAP product IDs (App Store / Play). Verify wired later.
    iap_ios_product_id: str = "market_radar.pro.monthly"
    iap_android_product_id: str = "market_radar.pro.monthly"
    # User preference defaults (overridable per user via /settings)
    default_brief_alarm_time: str = "07:00"
    default_timezone: str = "Asia/Seoul"
    # female → nova, male → onyx (see preference_service.resolve_tts_voice)
    default_tts_voice_gender: str = "female"
    # Push (FCM). Worker sends; API only registers tokens / enqueues.
    fcm_enabled: bool = False
    firebase_credentials_path: str = ""
    signal_push_daily_cap: int = 5
    # Push copy presentation limits (Unicode code points).
    push_title_max: int = 40
    push_body_max: int = 72
    # Signal-detail Ask AI (per-user explain). Explicit product exception to worker-only LLM.
    explain_daily_cap: int = 20
    explain_max_selection_chars: int = 280

    def tracked_x_accounts(self) -> tuple[str, ...]:
        parts = []
        for raw in self.x_track_accounts.split(","):
            name = raw.strip().lstrip("@")
            if name:
                parts.append(name)
        return tuple(parts)

    def issue_industry_keys(self) -> tuple[str, ...]:
        from app.pipeline.industries import parse_industry_keys

        return parse_industry_keys(self.issue_industries)

    def monitor_symbols(self) -> tuple[str, ...]:
        parts: list[str] = []
        for raw in self.monitor_set_symbols.split(","):
            sym = raw.strip().upper()
            if sym and sym not in parts:
                parts.append(sym)
        return tuple(parts)

    def macro_keywords(self) -> tuple[str, ...]:
        from app.pipeline.normalize import parse_macro_theme_keywords

        return parse_macro_theme_keywords(self.macro_theme_keywords)

    def macro_index_symbol_list(self) -> tuple[str, ...]:
        parts: list[str] = []
        for raw in self.macro_index_symbols.split(","):
            sym = raw.strip().upper()
            if sym and sym not in parts:
                parts.append(sym)
        return tuple(parts) if parts else ("SPY", "QQQ")

    def effective_daily_issue_soft_cap(self) -> int:
        """Soft publish pool for Issues; falls back to daily_signal_cap."""
        if self.daily_issue_soft_cap > 0:
            return self.daily_issue_soft_cap
        return self.daily_signal_cap

    @model_validator(mode="after")
    def _apply_test_fast_ingest(self) -> Self:
        if not self.test_fast_ingest:
            return self
        fast = max(1, int(self.test_ingest_interval_seconds))
        self.ingest_interval_seconds = fast
        self.x_accounts_interval_seconds = fast
        self.x_search_interval_seconds = fast
        self.x_topic_search_interval_seconds = fast
        self.rss_interval_seconds = fast
        self.kr_news_interval_seconds = fast
        self.dart_interval_seconds = fast
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
