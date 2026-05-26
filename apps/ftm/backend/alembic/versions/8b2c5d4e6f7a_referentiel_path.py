"""referentiel_path

Revision ID: 8b2c5d4e6f7a
Revises: 7a1e9b3c4d5f
Create Date: 2026-05-18 00:00:00.000000

Ajoute `projects.reference_path` : chemin du classeur Excel référentiel
(onglets ATM / BASL / LCC) introduit par le moteur de règles FTM Agent v4.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '8b2c5d4e6f7a'
down_revision: str | None = '7a1e9b3c4d5f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reference_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('reference_path')
