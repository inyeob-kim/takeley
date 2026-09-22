"""Additive: trend_status_updated_at for lifecycle grace / hysteresis."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260921_trend_lifecycle"
down_revision = "20260921_issue_push_copy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "issues" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("issues")}
    if "trend_status_updated_at" not in cols:
        op.add_column(
            "issues",
            sa.Column("trend_status_updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_issues_trend_status_updated_at",
            "issues",
            ["trend_status_updated_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "issues" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("issues")}
    if "trend_status_updated_at" in cols:
        op.drop_index("ix_issues_trend_status_updated_at", table_name="issues")
        op.drop_column("issues", "trend_status_updated_at")
