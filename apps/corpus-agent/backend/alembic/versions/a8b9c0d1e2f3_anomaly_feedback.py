"""anomaly feedback (motif de rejet / commentaire)

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-07-22 00:00:00.000000

Ajoute a `anomalies` une colonne `feedback` (texte libre) : motif saisi par le
relecteur au moment ou il agit sur l'anomalie — typiquement pourquoi il la
rejette (faux positif, hors perimetre, deja traite...). Vide par defaut.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("anomalies", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("feedback", sa.Text(), server_default="", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("anomalies", schema=None) as batch_op:
        batch_op.drop_column("feedback")
