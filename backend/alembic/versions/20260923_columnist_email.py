"""Optional columnist contact email + public toggle."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260923_columnist_email"
down_revision = "20260923_columnist_specialties"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "columnists" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("columnists")}
    if "contact_email" not in cols:
        op.add_column(
            "columnists", sa.Column("contact_email", sa.String(length=254), nullable=True)
        )
    if "show_email" not in cols:
        op.add_column(
            "columnists",
            sa.Column("show_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "columnists" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("columnists")}
    if "show_email" in cols:
        op.drop_column("columnists", "show_email")
    if "contact_email" in cols:
        op.drop_column("columnists", "contact_email")
