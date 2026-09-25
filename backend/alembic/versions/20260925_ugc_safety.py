"""UGC safety: comment status, reports, blocks, hides."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260925_ugc_safety"
down_revision = "20260923_columnist_profile_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "issue_comments" in tables:
        cols = {c["name"] for c in inspector.get_columns("issue_comments")}
        if "status" not in cols:
            op.add_column(
                "issue_comments",
                sa.Column(
                    "status",
                    sa.String(16),
                    nullable=False,
                    server_default="visible",
                ),
            )
            op.create_index(
                "ix_issue_comments_status", "issue_comments", ["status"]
            )

    if "content_reports" not in tables:
        op.create_table(
            "content_reports",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("reporter_id", sa.String(64), nullable=False),
            sa.Column("target_type", sa.String(16), nullable=False),
            sa.Column("target_id", sa.String(36), nullable=False),
            sa.Column("target_user_id", sa.String(64), nullable=False),
            sa.Column("reason", sa.String(32), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_content_reports_reporter_id", "content_reports", ["reporter_id"])
        op.create_index("ix_content_reports_target_type", "content_reports", ["target_type"])
        op.create_index("ix_content_reports_target_id", "content_reports", ["target_id"])
        op.create_index("ix_content_reports_target_user_id", "content_reports", ["target_user_id"])
        op.create_index("ix_content_reports_status", "content_reports", ["status"])
        op.create_index(
            "idx_content_reports_status_created",
            "content_reports",
            ["status", "created_at"],
        )
        op.create_index(
            "idx_content_reports_target",
            "content_reports",
            ["target_type", "target_id"],
        )

    if "user_blocks" not in tables:
        op.create_table(
            "user_blocks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("blocker_id", sa.String(64), nullable=False),
            sa.Column("blocked_id", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block_pair"),
        )
        op.create_index("ix_user_blocks_blocker_id", "user_blocks", ["blocker_id"])
        op.create_index("ix_user_blocks_blocked_id", "user_blocks", ["blocked_id"])

    if "hidden_contents" not in tables:
        op.create_table(
            "hidden_contents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(64), nullable=False),
            sa.Column("target_type", sa.String(16), nullable=False),
            sa.Column("target_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "user_id",
                "target_type",
                "target_id",
                name="uq_hidden_content_user_target",
            ),
        )
        op.create_index("ix_hidden_contents_user_id", "hidden_contents", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "hidden_contents" in tables:
        op.drop_table("hidden_contents")
    if "user_blocks" in tables:
        op.drop_table("user_blocks")
    if "content_reports" in tables:
        op.drop_table("content_reports")
    if "issue_comments" in tables:
        cols = {c["name"] for c in inspector.get_columns("issue_comments")}
        if "status" in cols:
            op.drop_index("ix_issue_comments_status", table_name="issue_comments")
            op.drop_column("issue_comments", "status")
