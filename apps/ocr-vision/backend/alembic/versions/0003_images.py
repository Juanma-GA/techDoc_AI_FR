"""images - illustrations extraites des PDF.

Revision ID: 0003_images
Revises: 0002_capitalisation
Create Date: 2026-07-21 00:00:00.000000

Table pour les images/illustrations extraites d'un PDF (fichiers JPG sur disque
sous data/storage/<project_table_id>/). Compatible SQLite et Postgres.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_images"
down_revision: str | None = "0002_capitalisation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extracted_image",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_table_id", sa.String(length=36), nullable=False),
        sa.Column("source_filename", sa.String(length=500), server_default="", nullable=False),
        sa.Column("filename", sa.String(length=300), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_table_id"], ["project_table.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extracted_image_project_table_id", "extracted_image", ["project_table_id"])


def downgrade() -> None:
    op.drop_index("ix_extracted_image_project_table_id", table_name="extracted_image")
    op.drop_table("extracted_image")
