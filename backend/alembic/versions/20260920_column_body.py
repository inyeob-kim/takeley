"""Add column_body for Issue long-form editorial."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260920_column_body"
down_revision = "20260920_metric_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("signals") as batch:
        batch.add_column(
            sa.Column("column_body", sa.Text(), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("signals") as batch:
        batch.drop_column("column_body")
