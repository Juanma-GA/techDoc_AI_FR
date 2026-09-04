"""module colorisation - couleur des pieces (par etat / type / profondeur).

Revision ID: 0004_colorization
Revises: 0003_modules
Create Date: 2026-06-01 00:00:02.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_colorization"
down_revision: str | None = "0003_modules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "colorization_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("diff_run_id", sa.Uuid(), nullable=True),
        sa.Column("strategy", sa.String(length=20), server_default="by_type", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("config_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("summary", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["structure_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["diff_run_id"], ["diff_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_colorization_runs_import", "colorization_runs", ["import_id"])
    op.create_index("ix_colorization_runs_diff", "colorization_runs", ["diff_run_id"])

    op.create_table(
        "colorization_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("rel_path", sa.String(length=1000), nullable=False),
        sa.Column("color_r", sa.Integer(), server_default="0", nullable=False),
        sa.Column("color_g", sa.Integer(), server_default="0", nullable=False),
        sa.Column("color_b", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["colorization_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_colorization_items_run", "colorization_items", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_colorization_items_run", table_name="colorization_items")
    op.drop_table("colorization_items")
    op.drop_index("ix_colorization_runs_diff", table_name="colorization_runs")
    op.drop_index("ix_colorization_runs_import", table_name="colorization_runs")
    op.drop_table("colorization_runs")
