"""Columnist public profile toggle (byline stays, profile is gated)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260923_columnist_profile_public"
down_revision = "20260923_columnist_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "columnists" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("columnists")}
    if "profile_public" not in cols:
        op.add_column(
            "columnists",
            sa.Column(
                "profile_public",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "columnists" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("columnists")}
    if "profile_public" in cols:
        op.drop_column("columnists", "profile_public")
