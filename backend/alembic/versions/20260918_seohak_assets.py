"""Add asset name_ko / exchange / market for 서학 UI.

Revision ID: 20260918_seohak_assets
Revises:
Create Date: 2026-09-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260918_seohak_assets"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("name_ko", sa.String(length=255), nullable=True))
    op.add_column("assets", sa.Column("exchange", sa.String(length=32), nullable=True))
    op.add_column(
        "assets",
        sa.Column("market", sa.String(length=16), nullable=True, server_default="US"),
    )


def downgrade() -> None:
    op.drop_column("assets", "market")
    op.drop_column("assets", "exchange")
    op.drop_column("assets", "name_ko")
