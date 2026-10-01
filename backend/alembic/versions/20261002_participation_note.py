"""Judgment note on participations + change logs + other-take exposures.

Revision ID: 20261002_participation_note
Revises: 20261001_news_notif_pref
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261002_participation_note"
down_revision = "20261001_news_notif_pref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    part_cols = {c["name"] for c in inspector.get_columns("participations")}
    if "note" not in part_cols:
        op.add_column(
            "participations",
            sa.Column("note", sa.Text(), nullable=True),
        )

    pref_cols = {c["name"] for c in inspector.get_columns("user_preferences")}
    if "participation_experiment_bucket" not in pref_cols:
        op.add_column(
            "user_preferences",
            sa.Column(
                "participation_experiment_bucket",
                sa.String(length=8),
                nullable=True,
            ),
        )

    tables = set(inspector.get_table_names())
    if "participation_change_logs" not in tables:
        op.create_table(
            "participation_change_logs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=64), nullable=False, index=True),
            sa.Column("signal_id", sa.String(length=36), nullable=False, index=True),
            sa.Column("from_option_id", sa.String(length=36), nullable=True),
            sa.Column("to_option_id", sa.String(length=36), nullable=False),
            sa.Column("changed_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["signal_id"], ["issues.id"]),
        )
        op.create_index(
            "idx_pcl_user_changed",
            "participation_change_logs",
            ["user_id", "changed_at"],
        )
        op.create_index(
            "idx_pcl_signal_changed",
            "participation_change_logs",
            ["signal_id", "changed_at"],
        )

    if "other_take_exposures" not in tables:
        op.create_table(
            "other_take_exposures",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=64), nullable=False, index=True),
            sa.Column("signal_id", sa.String(length=36), nullable=False, index=True),
            sa.Column("target_type", sa.String(length=16), nullable=False),
            sa.Column("target_id", sa.String(length=36), nullable=False),
            sa.Column("author_id", sa.String(length=64), nullable=False, index=True),
            sa.Column("session_key", sa.String(length=64), nullable=True),
            sa.Column("exposed_at", sa.DateTime(), nullable=False),
            sa.Column("skipped_at", sa.DateTime(), nullable=True),
            sa.Column("opened_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["signal_id"], ["issues.id"]),
        )
        op.create_index(
            "idx_ote_user_exposed",
            "other_take_exposures",
            ["user_id", "exposed_at"],
        )
        op.create_index(
            "idx_ote_user_signal",
            "other_take_exposures",
            ["user_id", "signal_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "other_take_exposures" in tables:
        op.drop_table("other_take_exposures")
    if "participation_change_logs" in tables:
        op.drop_table("participation_change_logs")

    pref_cols = {c["name"] for c in inspector.get_columns("user_preferences")}
    if "participation_experiment_bucket" in pref_cols:
        op.drop_column("user_preferences", "participation_experiment_bucket")

    part_cols = {c["name"] for c in inspector.get_columns("participations")}
    if "note" in part_cols:
        op.drop_column("participations", "note")
