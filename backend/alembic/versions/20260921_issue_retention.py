"""Issue follow/view retention tables + content_updated_at."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260921_issue_retention"
down_revision = "20260920_issue_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("signals") as batch:
        batch.add_column(sa.Column("content_updated_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_signals_content_updated_at", "signals", ["content_updated_at"]
    )
    op.execute(
        sa.text(
            "UPDATE signals SET content_updated_at = COALESCE(published_at, updated_at, first_seen_at) "
            "WHERE content_updated_at IS NULL"
        )
    )

    op.create_table(
        "issue_follows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "signal_id",
            sa.String(length=36),
            sa.ForeignKey("signals.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "signal_id", name="uq_issue_follow_user_signal"),
    )
    op.create_index(
        "idx_issue_follows_user_created", "issue_follows", ["user_id", "created_at"]
    )
    op.create_index("idx_issue_follows_signal", "issue_follows", ["signal_id"])
    op.create_index("ix_issue_follows_user_id", "issue_follows", ["user_id"])

    op.create_table(
        "issue_views",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "signal_id",
            sa.String(length=36),
            sa.ForeignKey("signals.id"),
            nullable=False,
        ),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "signal_id", name="uq_issue_view_user_signal"),
    )
    op.create_index(
        "idx_issue_views_user_seen", "issue_views", ["user_id", "last_seen_at"]
    )
    op.create_index("ix_issue_views_user_id", "issue_views", ["user_id"])
    op.create_index("ix_issue_views_last_seen_at", "issue_views", ["last_seen_at"])

    op.create_table(
        "issue_user_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "signal_id",
            sa.String(length=36),
            sa.ForeignKey("signals.id"),
            nullable=False,
        ),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "idx_issue_user_events_user_created",
        "issue_user_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_issue_user_events_signal_created",
        "issue_user_events",
        ["signal_id", "created_at"],
    )
    op.create_index(
        "idx_issue_user_events_event_created",
        "issue_user_events",
        ["event", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("issue_user_events")
    op.drop_table("issue_views")
    op.drop_table("issue_follows")
    op.drop_index("ix_signals_content_updated_at", table_name="signals")
    with op.batch_alter_table("signals") as batch:
        batch.drop_column("content_updated_at")
