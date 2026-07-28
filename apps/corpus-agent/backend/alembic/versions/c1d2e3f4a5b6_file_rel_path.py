"""file rel_path (identite stable pour la synchro de dossier connecte)

Revision ID: c1d2e3f4a5b6
Revises: b9c0d1e2f3a4
Create Date: 2026-07-28 00:00:00.000000

Ajoute a `files` une colonne `rel_path` (chemin relatif POSIX au dossier
connecte, nullable) : identifiant stable pour un fichier ingere via
`POST /projects/{id}/files/sync-folder`, en remplacement du nom seul (qui
collisionnait entre deux fichiers homonymes dans des sous-dossiers
differents). NULL pour un upload manuel (pas de notion de dossier) ou pour
un fichier ingere avant cette migration -- ces fichiers seront traites comme
"nouveaux" a la prochaine synchro de leur dossier (pas de reconstruction
retroactive possible : le chemin d'origine n'a jamais ete stocke).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.add_column(sa.Column("rel_path", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.drop_column("rel_path")
