"""Add image_url for Issue cover images."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260920_issue_image"
down_revision = "20260920_column_body"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("signals") as batch:
        batch.add_column(sa.Column("image_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("signals") as batch:
        batch.drop_column("image_url")
