"""project basl_columns + basl_header_rows

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-06-17 00:00:00.000000

Ajoute a `projects` deux colonnes nullable pour le mapping de la BASL, en
miroir du referentiel :
- `basl_columns` : registre JSON des colonnes BASL
  ([{"name","sheet","column","builtin"}]). Les 3 builtin (rechange, outillage,
  infrastructure) ciblent les colonnes contre lesquelles le check referentiel
  cross-checke. NULL ou colonne non mappee => repli sur l'union de toutes les
  cellules de la BASL (comportement historique).
- `basl_header_rows` : JSON {onglet: ligne(1-based)} de la ligne d'en-tete
  choisie par onglet. NULL => detection auto.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f7a8b9c0d1'
down_revision: str | None = 'd5e6f7a8b9c0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('basl_columns', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('basl_header_rows', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('basl_header_rows')
        batch_op.drop_column('basl_columns')
