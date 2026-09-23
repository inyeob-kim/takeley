"""TAKELEY columnists roster + issues.columnist_id."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260923_columnists"
down_revision = "20260921_trend_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "columnists" not in tables:
        op.create_table(
            "columnists",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("display_name", sa.String(length=128), nullable=False),
            sa.Column("headline", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("bio", sa.Text(), nullable=False, server_default=""),
            sa.Column("image_url", sa.String(length=1024), nullable=True),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="active",
            ),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        )
        op.create_index(
            "idx_columnists_status_sort",
            "columnists",
            ["status", "sort_order"],
        )

    if "issues" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("issues")}
    if "columnist_id" not in cols:
        op.add_column(
            "issues",
            sa.Column("columnist_id", sa.String(length=36), nullable=True),
        )
        op.create_index("ix_issues_columnist_id", "issues", ["columnist_id"])
        op.create_foreign_key(
            "fk_issues_columnist_id",
            "issues",
            "columnists",
            ["columnist_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "issues" in tables:
        cols = {c["name"] for c in inspector.get_columns("issues")}
        if "columnist_id" in cols:
            op.drop_constraint("fk_issues_columnist_id", "issues", type_="foreignkey")
            op.drop_index("ix_issues_columnist_id", table_name="issues")
            op.drop_column("issues", "columnist_id")
    if "columnists" in tables:
        op.drop_index("idx_columnists_status_sort", table_name="columnists")
        op.drop_table("columnists")
