"""project reference_columns

Revision ID: b3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-19 00:00:00.000000

Ajoute `projects.reference_columns` : registre JSON des colonnes de reference
du suivi/referentiel, une entree par colonne
({"name","sheet","column","builtin"}). Les 3 colonnes builtin (script,
granule_defaut, granule_pose) alimentent les checks script/granule ; l'analyste
peut en ajouter d'autres et les appeler depuis ses regles personnalisees.
NULL => les checks retombent sur les defauts de `rules.json`.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b3d4e5f6a7b8'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reference_columns', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('reference_columns')
