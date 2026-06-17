"""modules toolbox - diff, checks, conversion, replacement.

Revision ID: 0003_modules
Revises: 0002_tree_optimizer
Create Date: 2026-06-01 00:00:01.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_modules"
down_revision: str | None = "0002_tree_optimizer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Comparaison ---
    op.create_table(
        "diff_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("base_import_id", sa.Uuid(), nullable=False),
        sa.Column("other_import_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("summary", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["base_import_id"], ["structure_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["other_import_id"], ["structure_imports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diff_runs_base", "diff_runs", ["base_import_id"])
    op.create_index("ix_diff_runs_other", "diff_runs", ["other_import_id"])
    op.create_table(
        "diff_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("rel_path", sa.String(length=1000), nullable=False),
        sa.Column("change_type", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.Text(), server_default="", nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["diff_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diff_entries_run", "diff_entries", ["run_id"])
    op.create_index("ix_diff_entries_change", "diff_entries", ["change_type"])

    # --- Verifications ---
    op.create_table(
        "check_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("config_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("summary", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["structure_imports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_check_runs_import", "check_runs", ["import_id"])
    op.create_table(
        "check_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("rule", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="warning", nullable=False),
        sa.Column("rel_path", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["check_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_check_results_run", "check_results", ["run_id"])
    op.create_index("ix_check_results_rule", "check_results", ["rule"])

    # --- Conversion ---
    op.create_table(
        "conversion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("config_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("summary", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["structure_imports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversion_runs_import", "conversion_runs", ["import_id"])
    op.create_table(
        "conversion_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("source_path", sa.String(length=1000), nullable=False),
        sa.Column("target_path", sa.String(length=1000), nullable=False),
        sa.Column("source_ext", sa.String(length=40), server_default="", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["conversion_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversion_items_run", "conversion_items", ["run_id"])
    op.create_index("ix_conversion_items_status", "conversion_items", ["status"])

    # --- Remplacement ---
    op.create_table(
        "replacement_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("mapping_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("summary", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["structure_imports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_replacement_runs_import", "replacement_runs", ["import_id"])
    op.create_table(
        "replacement_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("occurrence_path", sa.String(length=1000), nullable=False),
        sa.Column("old_ref", sa.String(length=500), nullable=False),
        sa.Column("new_ref", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["replacement_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_replacement_items_run", "replacement_items", ["run_id"])
    op.create_index("ix_replacement_items_status", "replacement_items", ["status"])


def downgrade() -> None:
    op.drop_index("ix_replacement_items_status", table_name="replacement_items")
    op.drop_index("ix_replacement_items_run", table_name="replacement_items")
    op.drop_table("replacement_items")
    op.drop_index("ix_replacement_runs_import", table_name="replacement_runs")
    op.drop_table("replacement_runs")
    op.drop_index("ix_conversion_items_status", table_name="conversion_items")
    op.drop_index("ix_conversion_items_run", table_name="conversion_items")
    op.drop_table("conversion_items")
    op.drop_index("ix_conversion_runs_import", table_name="conversion_runs")
    op.drop_table("conversion_runs")
    op.drop_index("ix_check_results_rule", table_name="check_results")
    op.drop_index("ix_check_results_run", table_name="check_results")
    op.drop_table("check_results")
    op.drop_index("ix_check_runs_import", table_name="check_runs")
    op.drop_table("check_runs")
    op.drop_index("ix_diff_entries_change", table_name="diff_entries")
    op.drop_index("ix_diff_entries_run", table_name="diff_entries")
    op.drop_table("diff_entries")
    op.drop_index("ix_diff_runs_other", table_name="diff_runs")
    op.drop_index("ix_diff_runs_base", table_name="diff_runs")
    op.drop_table("diff_runs")
