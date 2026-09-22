"""Issue columns + participation / comments tables.

Revision ID: 20260920_issue_participation
Revises: 20260918_seohak_assets
Create Date: 2026-09-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260920_issue_participation"
down_revision = "20260918_seohak_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("category", sa.String(length=64), nullable=True))
    op.add_column("signals", sa.Column("topic", sa.String(length=128), nullable=True))
    op.add_column(
        "signals",
        sa.Column("trend_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "signals", sa.Column("participation_type", sa.String(length=32), nullable=True)
    )
    op.add_column("signals", sa.Column("participation_question", sa.Text(), nullable=True))
    op.add_column(
        "signals",
        sa.Column(
            "participation_suitable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "signals",
        sa.Column("impression_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "signals",
        sa.Column("open_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_signals_category", "signals", ["category"])
    op.create_index("ix_signals_topic", "signals", ["topic"])
    op.create_index("ix_signals_trend_score", "signals", ["trend_score"])

    op.create_table(
        "participation_options",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("signal_id", sa.String(length=36), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "idx_participation_options_signal_order",
        "participation_options",
        ["signal_id", "display_order"],
    )

    op.create_table(
        "participations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("signal_id", sa.String(length=36), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "option_id",
            sa.String(length=36),
            sa.ForeignKey("participation_options.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("signal_id", "user_id", name="uq_participation_signal_user"),
    )
    op.create_index(
        "idx_participations_user_created",
        "participations",
        ["user_id", "created_at"],
    )

    op.create_table(
        "issue_comments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("signal_id", sa.String(length=36), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "idx_issue_comments_signal_created",
        "issue_comments",
        ["signal_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("issue_comments")
    op.drop_table("participations")
    op.drop_table("participation_options")
    op.drop_index("ix_signals_trend_score", table_name="signals")
    op.drop_index("ix_signals_topic", table_name="signals")
    op.drop_index("ix_signals_category", table_name="signals")
    for col in (
        "open_count",
        "impression_count",
        "participation_suitable",
        "participation_question",
        "participation_type",
        "trend_score",
        "topic",
        "category",
    ):
        op.drop_column("signals", col)
