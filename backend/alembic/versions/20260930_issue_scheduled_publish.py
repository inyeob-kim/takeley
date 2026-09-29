"""Add issues.scheduled_publish_at for admin scheduled publish.

Revision ID: 20260930_issue_scheduled_publish
Revises: 20260927_discovery_modules
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260930_issue_scheduled_publish"
down_revision = "20260927_discovery_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("issues")}
    if "scheduled_publish_at" not in cols:
        op.add_column(
            "issues",
            sa.Column("scheduled_publish_at", sa.DateTime(), nullable=True),
        )
    indexes = {idx["name"] for idx in inspector.get_indexes("issues")}
    if "idx_issues_status_scheduled_publish" not in indexes:
        op.create_index(
            "idx_issues_status_scheduled_publish",
            "issues",
            ["status", "scheduled_publish_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("issues")}
    if "idx_issues_status_scheduled_publish" in indexes:
        op.drop_index("idx_issues_status_scheduled_publish", table_name="issues")
    cols = {c["name"] for c in inspector.get_columns("issues")}
    if "scheduled_publish_at" in cols:
        op.drop_column("issues", "scheduled_publish_at")
