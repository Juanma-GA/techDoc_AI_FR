"""etape 1 - colonnes nomenclature : piece remplacee, old/new PN & REV,
ref couleur, materiaux.

Revision ID: 0006_nomenclature_columns
Revises: 0005_pipeline
Create Date: 2026-07-08 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006_nomenclature_columns"
down_revision: str | None = "0005_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Nouvelles colonnes (nom, type, server_default) - ordre = ordre d'ajout.
_STR_COLUMNS: tuple[tuple[str, int], ...] = (
    ("old_pn", 500),
    ("new_pn", 500),
    ("old_rev", 60),
    ("new_rev", 60),
    ("color_ref", 200),
    ("materials", 200),
)


def upgrade() -> None:
    # server_default fourni => compatible SQLite ET Postgres sur table non vide.
    op.add_column(
        "nomenclature_items",
        sa.Column("replaced", sa.Boolean(), server_default="0", nullable=False),
    )
    for name, length in _STR_COLUMNS:
        op.add_column(
            "nomenclature_items",
            sa.Column(name, sa.String(length=length), server_default="", nullable=False),
        )
    op.create_index("ix_nomenclature_items_replaced", "nomenclature_items", ["replaced"])


def downgrade() -> None:
    op.drop_index("ix_nomenclature_items_replaced", table_name="nomenclature_items")
    for name, _ in reversed(_STR_COLUMNS):
        op.drop_column("nomenclature_items", name)
    op.drop_column("nomenclature_items", "replaced")
