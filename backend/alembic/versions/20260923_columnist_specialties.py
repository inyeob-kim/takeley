"""Columnist specialties list (separate from bio)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260923_columnist_specialties"
down_revision = "20260923_columnists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "columnists" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("columnists")}
    if "specialties" in cols:
        return
    dialect = bind.dialect.name
    col_type = sa.JSON()
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        col_type = JSONB()
    op.add_column("columnists", sa.Column("specialties", col_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "columnists" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("columnists")}
    if "specialties" in cols:
        op.drop_column("columnists", "specialties")
