"""anomaly category (checklist subject)

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-21 00:00:00.000000

Ajoute a `anomalies` une colonne `category` (le « Sujet » de la regle checklist
qui a produit l'anomalie). Dimension de regroupement des KPI en mode
checklist-only : le type d'anomalie unique est `personnalisee`, la categorie
porte le regroupement metier. NULL / vide => « Sans categorie » cote agregation.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("anomalies", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("category", sa.String(length=120), server_default="", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("anomalies", schema=None) as batch_op:
        batch_op.drop_column("category")
