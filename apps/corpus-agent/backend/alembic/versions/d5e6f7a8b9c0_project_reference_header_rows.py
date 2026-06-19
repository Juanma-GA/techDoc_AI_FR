"""project reference_header_rows

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-15 00:00:00.000000

Ajoute `projects.reference_header_rows` : JSON {onglet: ligne(1-based)} de la
ligne d'en-tete choisie par onglet du referentiel. Sert a lire les bons
libelles de colonnes dans l'editeur de mapping quand l'en-tete n'est pas la
ligne la plus large (detection auto prise en defaut). NULL => detection auto.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd5e6f7a8b9c0'
down_revision: str | None = 'c4d5e6f7a8b9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reference_header_rows', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('reference_header_rows')
