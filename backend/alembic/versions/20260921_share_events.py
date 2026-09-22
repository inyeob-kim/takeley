"""Add share attribution columns to issue_user_events.

Revision ID: 20260921_share_events
Revises: 20260921_contributor_data
Create Date: 2026-09-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_share_events"
down_revision: Union[str, None] = "20260921_events_nullable_signal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "issue_user_events",
        sa.Column("share_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "issue_user_events",
        sa.Column("ref_user_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "issue_user_events",
        sa.Column("share_intent", sa.String(length=16), nullable=True),
    )
    op.create_index(
        "ix_issue_user_events_share_id", "issue_user_events", ["share_id"]
    )
    op.create_index(
        "ix_issue_user_events_ref_user_id", "issue_user_events", ["ref_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_issue_user_events_ref_user_id", table_name="issue_user_events")
    op.drop_index("ix_issue_user_events_share_id", table_name="issue_user_events")
    op.drop_column("issue_user_events", "share_intent")
    op.drop_column("issue_user_events", "ref_user_id")
    op.drop_column("issue_user_events", "share_id")
