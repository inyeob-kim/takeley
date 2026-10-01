"""Add issues.content_kind for NEWS | ISSUE branch.

Revision ID: 20261001_issue_content_kind
Revises: 20260930_issue_scheduled_publish
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261001_issue_content_kind"
down_revision = "20260930_issue_scheduled_publish"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("issues")}
    if "content_kind" not in cols:
        op.add_column(
            "issues",
            sa.Column(
                "content_kind",
                sa.String(32),
                nullable=False,
                server_default="ISSUE",
            ),
        )
    indexes = {idx["name"] for idx in inspector.get_indexes("issues")}
    if "ix_issues_content_kind" not in indexes:
        op.create_index("ix_issues_content_kind", "issues", ["content_kind"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("issues")}
    if "ix_issues_content_kind" in indexes:
        op.drop_index("ix_issues_content_kind", table_name="issues")
    cols = {c["name"] for c in inspector.get_columns("issues")}
    if "content_kind" in cols:
        op.drop_column("issues", "content_kind")
