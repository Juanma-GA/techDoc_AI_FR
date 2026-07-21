"""capitalisation - templates / projets / tables / lignes extraites.

Revision ID: 0002_capitalisation
Revises: 0001_initial
Create Date: 2026-07-20 00:00:00.000000

Tables pour capitaliser les donnees extraites par projet. Compatible SQLite
et Postgres (types portables : String(36) pour les UUID, JSON, DateTime tz).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_capitalisation"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "table_template",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("columns", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "project",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "project_table",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["table_template.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_table_project_id", "project_table", ["project_id"])

    op.create_table(
        "extracted_row",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_table_id", sa.String(length=36), nullable=False),
        sa.Column("source_filename", sa.String(length=500), server_default="", nullable=False),
        sa.Column("values", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_table_id"], ["project_table.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extracted_row_project_table_id", "extracted_row", ["project_table_id"])


def downgrade() -> None:
    op.drop_index("ix_extracted_row_project_table_id", table_name="extracted_row")
    op.drop_table("extracted_row")
    op.drop_index("ix_project_table_project_id", table_name="project_table")
    op.drop_table("project_table")
    op.drop_table("project")
    op.drop_table("table_template")
