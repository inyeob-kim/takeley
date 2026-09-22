"""Add column author byline fields on issues.

Revision ID: 20260921_column_author
Revises: 20260921_share_events
Create Date: 2026-09-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_column_author"
down_revision: Union[str, None] = "20260921_share_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("issues") as batch:
        batch.add_column(
            sa.Column("column_author_name", sa.String(length=128), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "column_author_image_url", sa.String(length=1024), nullable=True
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("issues") as batch:
        batch.drop_column("column_author_image_url")
        batch.drop_column("column_author_name")
