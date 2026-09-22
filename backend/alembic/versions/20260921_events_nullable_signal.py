"""Make issue_user_events.signal_id nullable for Contributor lifecycle events."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260921_events_nullable_signal"
down_revision = "20260921_contributor_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("issue_user_events") as batch:
        batch.alter_column(
            "signal_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )


def downgrade() -> None:
    # Cannot safely restore NOT NULL if null rows exist.
    with op.batch_alter_table("issue_user_events") as batch:
        batch.alter_column(
            "signal_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
