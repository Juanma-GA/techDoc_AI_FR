"""etape 1 - colonnes slots + mono-corps : identification des pieces mono-corps.

Trois colonnes 'slot_1/2/3' (contenu brut des colonnes Slot N de l'onglet
Materiaux) + un drapeau 'mono_body' (piece mono-corps = un seul slot renseigne
OU tous les slots renseignes identiques).

Revision ID: 0008_nomenclature_slots
Revises: 0007_nomenclature_to_treat_value
Create Date: 2026-07-20 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0008_nomenclature_slots"
down_revision: str | None = "0007_nomenclature_to_treat_value"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SLOT_COLUMNS: tuple[str, ...] = ("slot_1", "slot_2", "slot_3")


def upgrade() -> None:
    for name in _SLOT_COLUMNS:
        op.add_column(
            "nomenclature_items",
            sa.Column(name, sa.String(length=200), server_default="", nullable=False),
        )
    op.add_column(
        "nomenclature_items",
        sa.Column("mono_body", sa.Boolean(), server_default="0", nullable=False),
    )
    op.create_index("ix_nomenclature_items_mono_body", "nomenclature_items", ["mono_body"])


def downgrade() -> None:
    op.drop_index("ix_nomenclature_items_mono_body", table_name="nomenclature_items")
    op.drop_column("nomenclature_items", "mono_body")
    for name in reversed(_SLOT_COLUMNS):
        op.drop_column("nomenclature_items", name)
