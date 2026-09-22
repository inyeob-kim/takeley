"""Optional admin push copy overrides on issues.

Revision ID: 20260921_issue_push_copy
Revises: 20260921_column_author
Create Date: 2026-09-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_issue_push_copy"
down_revision: Union[str, None] = "20260921_column_author"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "issues",
        sa.Column("push_title", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "issues",
        sa.Column("push_body", sa.String(length=160), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("issues", "push_body")
    op.drop_column("issues", "push_title")
