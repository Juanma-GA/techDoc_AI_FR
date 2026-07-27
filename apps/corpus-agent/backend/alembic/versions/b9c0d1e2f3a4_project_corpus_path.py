"""project corpus_path (dossier connecte)

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-07-23 00:00:00.000000

Ajoute a `projects` une colonne `corpus_path` (chemin local, nullable) : dossier
corpus connecte — typiquement un dossier OneDrive synchronise — dont les fichiers
sont ingeres via `POST /projects/{id}/files/sync-folder`, en alternative a
l'upload manuel. NULL = aucun dossier connecte.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9c0d1e2f3a4"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("corpus_path", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("corpus_path")
