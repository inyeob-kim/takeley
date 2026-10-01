"""Add news_notifications_enabled to user_preferences.

Revision ID: 20261001_news_notif_pref
Revises: 20261001_issue_content_kind
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261001_news_notif_pref"
down_revision = "20261001_issue_content_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("user_preferences")}
    if "news_notifications_enabled" not in cols:
        op.add_column(
            "user_preferences",
            sa.Column(
                "news_notifications_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("user_preferences")}
    if "news_notifications_enabled" in cols:
        op.drop_column("user_preferences", "news_notifications_enabled")
