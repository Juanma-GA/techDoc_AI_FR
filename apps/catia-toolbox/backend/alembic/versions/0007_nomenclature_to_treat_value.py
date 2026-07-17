"""etape 1 - colonne 'to_treat_value' : contenu brut de la cellule A TRAITER.

Revision ID: 0007_nomenclature_to_treat_value
Revises: 0006_nomenclature_columns
Create Date: 2026-07-10 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0007_nomenclature_to_treat_value"
down_revision: str | None = "0006_nomenclature_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nomenclature_items",
        sa.Column("to_treat_value", sa.String(length=200), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("nomenclature_items", "to_treat_value")
