"""Additive: metric_snapshots for engagement velocity.

Revision ID: 20260920_metric_snapshots
Revises: 20260920_issue_pipeline_v2
Create Date: 2026-09-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260920_metric_snapshots"
down_revision = "20260920_issue_pipeline_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "metric_snapshots" in insp.get_table_names():
        return
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("signal_id", sa.String(length=36), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("reply_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retweet_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quote_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("engagement_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "idx_metric_snapshots_signal_captured",
        "metric_snapshots",
        ["signal_id", "captured_at"],
    )
    op.create_index("ix_metric_snapshots_signal_id", "metric_snapshots", ["signal_id"])
    op.create_index("ix_metric_snapshots_captured_at", "metric_snapshots", ["captured_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "metric_snapshots" not in insp.get_table_names():
        return
    op.drop_table("metric_snapshots")
