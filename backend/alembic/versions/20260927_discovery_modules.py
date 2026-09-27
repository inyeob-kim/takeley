"""Discovery modules, pipeline controls, and admin RSS feeds."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_discovery_modules"
down_revision = "20260925_ugc_safety"
branch_labels = None
depends_on = None

_MODULE_IDS = (
    ("x", True, None),
    ("rss", False, 3600),
    ("trends", False, None),
    ("reddit", False, None),
    ("hacker_news", False, None),
    ("official", False, None),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "discovery_modules" not in tables:
        op.create_table(
            "discovery_modules",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("interval_seconds", sa.Integer(), nullable=True),
            sa.Column("last_started_at", sa.DateTime(), nullable=True),
            sa.Column("last_finished_at", sa.DateTime(), nullable=True),
            sa.Column("last_status", sa.String(16), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("items_fetched", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("items_inserted", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("items_duplicate", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("items_failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        )
        modules = sa.table(
            "discovery_modules",
            sa.column("id", sa.String),
            sa.column("enabled", sa.Boolean),
            sa.column("interval_seconds", sa.Integer),
        )
        op.bulk_insert(
            modules,
            [
                {
                    "id": module_id,
                    "enabled": enabled,
                    "interval_seconds": interval,
                }
                for module_id, enabled, interval in _MODULE_IDS
            ],
        )

    if "pipeline_controls" not in tables:
        op.create_table(
            "pipeline_controls",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column(
                "process_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "trend_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "push_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        controls = sa.table(
            "pipeline_controls",
            sa.column("id", sa.String),
            sa.column("process_enabled", sa.Boolean),
            sa.column("trend_enabled", sa.Boolean),
            sa.column("push_enabled", sa.Boolean),
        )
        op.bulk_insert(
            controls,
            [
                {
                    "id": "default",
                    "process_enabled": True,
                    "trend_enabled": True,
                    "push_enabled": True,
                }
            ],
        )

    if "rss_feeds" not in tables:
        op.create_table(
            "rss_feeds",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("url", sa.String(1024), nullable=False),
            sa.Column("language", sa.String(16), nullable=False, server_default=""),
            sa.Column("category", sa.String(32), nullable=False, server_default=""),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("etag", sa.String(256), nullable=True),
            sa.Column("last_modified", sa.String(128), nullable=True),
            sa.Column("cursor_value", sa.String(255), nullable=True),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("last_success_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_table("rss_feeds")
    op.drop_table("pipeline_controls")
    op.drop_table("discovery_modules")
