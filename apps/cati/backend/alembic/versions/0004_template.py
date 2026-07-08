"""cati - table cati_template (templates Excel geres dans l'UI).

Revision ID: 0004_template
Revises: 0003_challenge
Create Date: 2026-07-07 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_template"
down_revision: str | None = "0003_challenge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cati_template",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("filename", sa.String(length=500), server_default="", nullable=False),
        sa.Column("storage_path", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("sheet_name", sa.String(length=120), server_default="Catalogue", nullable=False),
        sa.Column("header_row", sa.Integer(), server_default="1", nullable=False),
        sa.Column("data_start_row", sa.Integer(), server_default="2", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("cati_template")
