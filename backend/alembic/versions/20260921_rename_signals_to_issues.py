"""Rename signals table to issues (TAKELEY Issue store).

Child FK column names remain `signal_id` (points at issues.id).
Historical migrations that referenced `signals` stay unchanged.
"""

from __future__ import annotations

from alembic import op

revision = "20260921_rename_signals_to_issues"
down_revision = "20260921_issue_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = __import__("sqlalchemy", fromlist=["inspect"]).inspect(bind)
    tables = set(inspector.get_table_names())
    if "signals" in tables and "issues" not in tables:
        op.rename_table("signals", "issues")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = __import__("sqlalchemy", fromlist=["inspect"]).inspect(bind)
    tables = set(inspector.get_table_names())
    if "issues" in tables and "signals" not in tables:
        op.rename_table("issues", "signals")
