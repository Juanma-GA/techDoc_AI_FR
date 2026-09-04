"""pipeline 5 etapes - identification (nomenclature), SMGXML, QC checklist.

Revision ID: 0005_pipeline
Revises: 0004_colorization
Create Date: 2026-06-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_pipeline"
down_revision: str | None = "0004_colorization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Etape 1 : nomenclature ---------------------------------------------
    op.create_table(
        "nomenclature_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_ref", sa.Text(), server_default="", nullable=False),
        sa.Column("sheet", sa.String(length=200), server_default="", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("summary", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "nomenclature_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("catpart", sa.String(length=500), server_default="", nullable=False),
        sa.Column("designation", sa.Text(), server_default="", nullable=False),
        sa.Column("sin", sa.String(length=200), server_default="", nullable=False),
        sa.Column("version", sa.String(length=60), server_default="", nullable=False),
        sa.Column("to_treat", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("mono_color", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("color_r", sa.Integer(), server_default="0", nullable=False),
        sa.Column("color_g", sa.Integer(), server_default="0", nullable=False),
        sa.Column("color_b", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_row", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["nomenclature_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nomenclature_items_run", "nomenclature_items", ["run_id"])
    op.create_index("ix_nomenclature_items_catpart", "nomenclature_items", ["catpart"])
    op.create_index("ix_nomenclature_items_sin", "nomenclature_items", ["sin"])
    op.create_index("ix_nomenclature_items_to_treat", "nomenclature_items", ["to_treat"])

    # --- Etapes 3 & 4 : SMGXML ----------------------------------------------
    op.create_table(
        "smgxml_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_ref", sa.Text(), server_default="", nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="planned", nullable=False),
        sa.Column("applied", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("backup_path", sa.Text(), server_default="", nullable=False),
        sa.Column("output_path", sa.Text(), server_default="", nullable=False),
        sa.Column("config_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("summary", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "smgxml_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(length=500), server_default="", nullable=False),
        sa.Column("change_type", sa.String(length=16), nullable=False),
        sa.Column("old_value", sa.Text(), server_default="", nullable=False),
        sa.Column("new_value", sa.Text(), server_default="", nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["smgxml_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_smgxml_changes_run", "smgxml_changes", ["run_id"])

    # --- Etape 5 : QC checklist ---------------------------------------------
    op.create_table(
        "qc_checklists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "qc_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("checklist_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), server_default="", nullable=False),
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("comment", sa.Text(), server_default="", nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["checklist_id"], ["qc_checklists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qc_items_checklist", "qc_items", ["checklist_id"])
    op.create_index("ix_qc_items_status", "qc_items", ["status"])


def downgrade() -> None:
    op.drop_table("qc_items")
    op.drop_table("qc_checklists")
    op.drop_table("smgxml_changes")
    op.drop_table("smgxml_runs")
    op.drop_table("nomenclature_items")
    op.drop_table("nomenclature_runs")
