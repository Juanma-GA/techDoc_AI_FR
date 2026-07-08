"""cati - table cati_profile + colonne profile_id sur cati_document.

Revision ID: 0005_profile
Revises: 0004_template
Create Date: 2026-07-08 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_profile"
down_revision: str | None = "0004_template"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cati_profile",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("pdf_map", sa.Text(), server_default="{}", nullable=False),
        sa.Column("excel_map", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("cati_document", sa.Column("profile_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("cati_document", "profile_id")
    op.drop_table("cati_profile")
