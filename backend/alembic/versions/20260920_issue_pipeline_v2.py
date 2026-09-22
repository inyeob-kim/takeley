"""Additive Issue Pipeline V2 columns + Alembic drift fix.

Revision ID: 20260920_issue_pipeline_v2
Revises: 20260920_issue_participation
Create Date: 2026-09-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260920_issue_pipeline_v2"
down_revision = "20260920_issue_participation"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    cols = _columns("signals")
    if "is_trending" not in cols:
        op.add_column(
            "signals",
            sa.Column(
                "is_trending",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.create_index("ix_signals_is_trending", "signals", ["is_trending"])
    if "source_reply_peak" not in cols:
        op.add_column(
            "signals",
            sa.Column(
                "source_reply_peak",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    if "lifecycle" not in cols:
        op.add_column(
            "signals",
            sa.Column("lifecycle", sa.String(length=32), nullable=True),
        )
        op.create_index("ix_signals_lifecycle", "signals", ["lifecycle"])
    if "trend_status" not in cols:
        op.add_column(
            "signals",
            sa.Column(
                "trend_status",
                sa.String(length=32),
                nullable=True,
                server_default="NORMAL",
            ),
        )

    src_cols = _columns("signal_sources")
    if "trust_tier" not in src_cols:
        op.add_column(
            "signal_sources",
            sa.Column("trust_tier", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    src_cols = _columns("signal_sources")
    if "trust_tier" in src_cols:
        op.drop_column("signal_sources", "trust_tier")
    cols = _columns("signals")
    if "lifecycle" in cols:
        op.drop_index("ix_signals_lifecycle", table_name="signals")
        op.drop_column("signals", "lifecycle")
    if "trend_status" in cols:
        op.drop_column("signals", "trend_status")
    if "is_trending" in cols:
        op.drop_index("ix_signals_is_trending", table_name="signals")
        op.drop_column("signals", "is_trending")
    if "source_reply_peak" in cols:
        op.drop_column("signals", "source_reply_peak")
