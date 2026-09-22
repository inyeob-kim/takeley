"""Contributor data layer: users fields, applications, issue_takes, reactions, events.take_id.

Additive only. No Reward schema. featured_at is reserved (no Featured logic).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260921_contributor_data"
down_revision = "20260921_rename_signals_to_issues"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users (additive Contributor fields) ---
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("display_name", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column(
                "contributor_status",
                sa.String(length=32),
                nullable=False,
                server_default="NONE",
            )
        )
        batch.add_column(
            sa.Column("contributor_approved_at", sa.DateTime(), nullable=True)
        )
    op.create_index(
        "ix_users_contributor_status", "users", ["contributor_status"]
    )
    # Ensure existing rows are NONE even if server_default was skipped on some backends.
    op.execute(
        sa.text(
            "UPDATE users SET contributor_status = 'NONE' "
            "WHERE contributor_status IS NULL OR contributor_status = ''"
        )
    )

    # --- contributor_applications ---
    op.create_table(
        "contributor_applications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("motivation", sa.Text(), nullable=False, server_default=""),
        sa.Column("interests", sa.Text(), nullable=False, server_default=""),
        sa.Column("sample_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "idx_contributor_applications_user_created",
        "contributor_applications",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_contributor_applications_status",
        "contributor_applications",
        ["status"],
    )
    op.create_index(
        "ix_contributor_applications_user_id",
        "contributor_applications",
        ["user_id"],
    )

    # --- issue_takes (domain FK: issue_id → issues.id) ---
    op.create_table(
        "issue_takes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "issue_id",
            sa.String(length=36),
            sa.ForeignKey("issues.id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_urls", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column(
            "view_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "reaction_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("featured_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_issue_takes_issue_id", "issue_takes", ["issue_id"])
    op.create_index("ix_issue_takes_author_id", "issue_takes", ["author_id"])
    op.create_index("ix_issue_takes_status", "issue_takes", ["status"])
    op.create_index(
        "ix_issue_takes_published_at", "issue_takes", ["published_at"]
    )
    op.create_index(
        "idx_issue_takes_issue_status", "issue_takes", ["issue_id", "status"]
    )
    op.create_index(
        "idx_issue_takes_author_created",
        "issue_takes",
        ["author_id", "created_at"],
    )

    # --- issue_take_reactions ---
    op.create_table(
        "issue_take_reactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "take_id",
            sa.String(length=36),
            sa.ForeignKey("issue_takes.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "take_id", "user_id", name="uq_issue_take_reaction_user"
        ),
    )
    op.create_index(
        "idx_issue_take_reactions_take", "issue_take_reactions", ["take_id"]
    )
    op.create_index(
        "ix_issue_take_reactions_take_id", "issue_take_reactions", ["take_id"]
    )
    op.create_index(
        "ix_issue_take_reactions_user_id", "issue_take_reactions", ["user_id"]
    )

    # --- issue_user_events.take_id (nullable, existing rows stay NULL) ---
    with op.batch_alter_table("issue_user_events") as batch:
        batch.add_column(
            sa.Column(
                "take_id",
                sa.String(length=36),
                sa.ForeignKey("issue_takes.id"),
                nullable=True,
            )
        )
    op.create_index(
        "ix_issue_user_events_take_id", "issue_user_events", ["take_id"]
    )
    op.create_index(
        "idx_issue_user_events_take_created",
        "issue_user_events",
        ["take_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_issue_user_events_take_created", table_name="issue_user_events"
    )
    op.drop_index("ix_issue_user_events_take_id", table_name="issue_user_events")
    with op.batch_alter_table("issue_user_events") as batch:
        batch.drop_column("take_id")

    op.drop_table("issue_take_reactions")
    op.drop_table("issue_takes")
    op.drop_table("contributor_applications")

    op.drop_index("ix_users_contributor_status", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("contributor_approved_at")
        batch.drop_column("contributor_status")
        batch.drop_column("display_name")
