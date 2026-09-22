from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=not settings.database_url.startswith("sqlite"),
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models so metadata is registered before create_all.
    from app.db import models  # noqa: F401
    from app.services.push_template_service import ensure_default_templates

    # Must run before create_all so we don't create an empty `issues` beside `signals`.
    _rename_signals_table_if_needed()
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema_patches()
    db = SessionLocal()
    try:
        ensure_default_templates(db)
    finally:
        db.close()


def _sqlite_table_names(conn) -> set[str]:
    rows = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def _rename_signals_table_if_needed() -> None:
    """Local SQLite path: rename legacy `signals` → `issues` before ORM create_all."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        tables = _sqlite_table_names(conn)
        if "signals" in tables and "issues" not in tables:
            conn.exec_driver_sql("ALTER TABLE signals RENAME TO issues")


def _ensure_sqlite_schema_patches() -> None:
    """SQLite create_all does not ALTER existing tables — add missing cols."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        briefs = conn.exec_driver_sql("PRAGMA table_info(market_briefs)").fetchall()
        brief_cols = {r[1] for r in briefs}
        if brief_cols:
            if "audio_url" not in brief_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE market_briefs ADD COLUMN audio_url VARCHAR(1024)"
                )
            if "audio_status" not in brief_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE market_briefs ADD COLUMN audio_status VARCHAR(32) DEFAULT 'none'"
                )

        issues = conn.exec_driver_sql("PRAGMA table_info(issues)").fetchall()
        issue_cols = {r[1] for r in issues}
        if issue_cols and "published_at" not in issue_cols:
            conn.exec_driver_sql(
                "ALTER TABLE issues ADD COLUMN published_at DATETIME"
            )
        if issue_cols and "key_points" not in issue_cols:
            conn.exec_driver_sql(
                "ALTER TABLE issues ADD COLUMN key_points JSON DEFAULT '[]'"
            )
        if issue_cols and "emphasis" not in issue_cols:
            conn.exec_driver_sql(
                "ALTER TABLE issues ADD COLUMN emphasis JSON DEFAULT '{}'"
            )
        if issue_cols and "content_type" not in issue_cols:
            conn.exec_driver_sql(
                "ALTER TABLE issues ADD COLUMN content_type VARCHAR(32) DEFAULT 'REPORT'"
            )
        if issue_cols and "evidence_level" not in issue_cols:
            conn.exec_driver_sql(
                "ALTER TABLE issues "
                "ADD COLUMN evidence_level VARCHAR(32) DEFAULT 'UNVERIFIED'"
            )
        for col, ddl in (
            ("category", "ALTER TABLE issues ADD COLUMN category VARCHAR(64)"),
            ("topic", "ALTER TABLE issues ADD COLUMN topic VARCHAR(128)"),
            (
                "trend_score",
                "ALTER TABLE issues ADD COLUMN trend_score FLOAT DEFAULT 0",
            ),
            (
                "is_trending",
                "ALTER TABLE issues ADD COLUMN is_trending BOOLEAN DEFAULT 0",
            ),
            (
                "source_reply_peak",
                "ALTER TABLE issues ADD COLUMN source_reply_peak INTEGER DEFAULT 0",
            ),
            (
                "participation_type",
                "ALTER TABLE issues ADD COLUMN participation_type VARCHAR(32)",
            ),
            (
                "participation_question",
                "ALTER TABLE issues ADD COLUMN participation_question TEXT",
            ),
            (
                "participation_suitable",
                "ALTER TABLE issues ADD COLUMN participation_suitable BOOLEAN DEFAULT 0",
            ),
            (
                "impression_count",
                "ALTER TABLE issues ADD COLUMN impression_count INTEGER DEFAULT 0",
            ),
            (
                "open_count",
                "ALTER TABLE issues ADD COLUMN open_count INTEGER DEFAULT 0",
            ),
            (
                "lifecycle",
                "ALTER TABLE issues ADD COLUMN lifecycle VARCHAR(32)",
            ),
            (
                "trend_status",
                "ALTER TABLE issues ADD COLUMN trend_status VARCHAR(32) DEFAULT 'NORMAL'",
            ),
            (
                "trend_status_updated_at",
                "ALTER TABLE issues ADD COLUMN trend_status_updated_at DATETIME",
            ),
            (
                "column_body",
                "ALTER TABLE issues ADD COLUMN column_body TEXT DEFAULT ''",
            ),
            (
                "column_author_name",
                "ALTER TABLE issues ADD COLUMN column_author_name VARCHAR(128)",
            ),
            (
                "column_author_image_url",
                "ALTER TABLE issues ADD COLUMN column_author_image_url VARCHAR(1024)",
            ),
            (
                "image_url",
                "ALTER TABLE issues ADD COLUMN image_url VARCHAR(1024)",
            ),
            (
                "content_updated_at",
                "ALTER TABLE issues ADD COLUMN content_updated_at DATETIME",
            ),
            (
                "show_sources",
                "ALTER TABLE issues ADD COLUMN show_sources BOOLEAN DEFAULT 0",
            ),
            (
                "push_title",
                "ALTER TABLE issues ADD COLUMN push_title VARCHAR(80)",
            ),
            (
                "push_body",
                "ALTER TABLE issues ADD COLUMN push_body VARCHAR(160)",
            ),
        ):
            if issue_cols and col not in issue_cols:
                conn.exec_driver_sql(ddl)

        # Backfill content_updated_at for existing rows (full schema only).
        if issue_cols and {"content_updated_at", "updated_at", "first_seen_at"} <= issue_cols:
            conn.exec_driver_sql(
                "UPDATE issues SET content_updated_at = COALESCE(published_at, updated_at, first_seen_at) "
                "WHERE content_updated_at IS NULL"
            )

        # show_sources defaults off; leave NULL as off.
        issue_cols_after = {
            r[1] for r in conn.exec_driver_sql("PRAGMA table_info(issues)").fetchall()
        }
        if "show_sources" in issue_cols_after:
            conn.exec_driver_sql(
                "UPDATE issues SET show_sources = 0 WHERE show_sources IS NULL"
            )

        # Rename legacy English categories → Korean display labels.
        if "category" in issue_cols_after:
            for old, new in (
                ("Politics", "정치"),
                ("Economy", "경제"),
                ("Finance", "금융"),
                ("Tech", "기술"),
                ("Technology", "기술"),
                ("Society", "사회"),
                ("World", "국제"),
                ("International", "국제"),
                ("Culture", "문화"),
                ("Sports", "스포츠"),
                ("Sport", "스포츠"),
                ("Entertainment", "엔터"),
            ):
                conn.exec_driver_sql(
                    f"UPDATE issues SET category = '{new}' WHERE category = '{old}'"
                )

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS issue_follows (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                signal_id VARCHAR(36) NOT NULL,
                created_at DATETIME NOT NULL,
                UNIQUE (user_id, signal_id),
                FOREIGN KEY(signal_id) REFERENCES issues (id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS issue_views (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                signal_id VARCHAR(36) NOT NULL,
                first_seen_at DATETIME NOT NULL,
                last_seen_at DATETIME NOT NULL,
                UNIQUE (user_id, signal_id),
                FOREIGN KEY(signal_id) REFERENCES issues (id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS issue_user_events (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                signal_id VARCHAR(36),
                event VARCHAR(32) NOT NULL,
                created_at DATETIME NOT NULL,
                take_id VARCHAR(36),
                FOREIGN KEY(signal_id) REFERENCES issues (id)
            )
            """
        )

        # --- Contributor data layer (additive; create takes before events.take_id FK use) ---
        users = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        user_cols = {r[1] for r in users}
        if user_cols:
            if "display_name" not in user_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN display_name VARCHAR(64)"
                )
            if "contributor_status" not in user_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE users "
                    "ADD COLUMN contributor_status VARCHAR(32) DEFAULT 'NONE'"
                )
                conn.exec_driver_sql(
                    "UPDATE users SET contributor_status = 'NONE' "
                    "WHERE contributor_status IS NULL OR contributor_status = ''"
                )
            if "contributor_approved_at" not in user_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN contributor_approved_at DATETIME"
                )

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS contributor_applications (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                motivation TEXT NOT NULL DEFAULT '',
                interests TEXT NOT NULL DEFAULT '',
                sample_text TEXT NOT NULL DEFAULT '',
                status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
                admin_note TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                reviewed_at DATETIME,
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS issue_takes (
                id VARCHAR(36) PRIMARY KEY,
                issue_id VARCHAR(36) NOT NULL,
                author_id VARCHAR(36) NOT NULL,
                title VARCHAR(120) NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                source_urls JSON NOT NULL DEFAULT '[]',
                status VARCHAR(32) NOT NULL DEFAULT 'draft',
                admin_note TEXT,
                view_count INTEGER NOT NULL DEFAULT 0,
                reaction_count INTEGER NOT NULL DEFAULT 0,
                featured_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                published_at DATETIME,
                FOREIGN KEY(issue_id) REFERENCES issues (id),
                FOREIGN KEY(author_id) REFERENCES users (id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS issue_take_reactions (
                id VARCHAR(36) PRIMARY KEY,
                take_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL,
                UNIQUE (take_id, user_id),
                FOREIGN KEY(take_id) REFERENCES issue_takes (id)
            )
            """
        )

        events = conn.exec_driver_sql(
            "PRAGMA table_info(issue_user_events)"
        ).fetchall()
        event_cols = {r[1] for r in events}
        if event_cols and "take_id" not in event_cols:
            conn.exec_driver_sql(
                "ALTER TABLE issue_user_events ADD COLUMN take_id VARCHAR(36)"
            )
        if event_cols and "share_id" not in event_cols:
            conn.exec_driver_sql(
                "ALTER TABLE issue_user_events ADD COLUMN share_id VARCHAR(36)"
            )
        if event_cols and "ref_user_id" not in event_cols:
            conn.exec_driver_sql(
                "ALTER TABLE issue_user_events ADD COLUMN ref_user_id VARCHAR(64)"
            )
        if event_cols and "share_intent" not in event_cols:
            conn.exec_driver_sql(
                "ALTER TABLE issue_user_events ADD COLUMN share_intent VARCHAR(16)"
            )

        sources = conn.exec_driver_sql("PRAGMA table_info(signal_sources)").fetchall()
        source_cols = {r[1] for r in sources}
        if source_cols and "trust_tier" not in source_cols:
            conn.exec_driver_sql(
                "ALTER TABLE signal_sources ADD COLUMN trust_tier VARCHAR(32)"
            )

        prefs = conn.exec_driver_sql("PRAGMA table_info(user_preferences)").fetchall()
        pref_cols = {r[1] for r in prefs}
        if pref_cols and "tts_voice_gender" not in pref_cols:
            conn.exec_driver_sql(
                "ALTER TABLE user_preferences "
                "ADD COLUMN tts_voice_gender VARCHAR(16) DEFAULT 'female'"
            )

        assets = conn.exec_driver_sql("PRAGMA table_info(assets)").fetchall()
        asset_cols = {r[1] for r in assets}
        if asset_cols and "name_ko" not in asset_cols:
            conn.exec_driver_sql(
                "ALTER TABLE assets ADD COLUMN name_ko VARCHAR(255)"
            )
        if asset_cols and "exchange" not in asset_cols:
            conn.exec_driver_sql(
                "ALTER TABLE assets ADD COLUMN exchange VARCHAR(32)"
            )
        if asset_cols and "market" not in asset_cols:
            conn.exec_driver_sql(
                "ALTER TABLE assets ADD COLUMN market VARCHAR(16) DEFAULT 'US'"
            )
