"""drop_dmc_reference

Revision ID: 9c3d6e5f7a8b
Revises: 8b2c5d4e6f7a
Create Date: 2026-05-18 00:00:00.000000

Retire les colonnes `projects.dmc_reference_*` : le mécanisme de référentiel
DMC v3 est remplacé par le référentiel unique v4 (`projects.reference_path`).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '9c3d6e5f7a8b'
down_revision: str | None = '8b2c5d4e6f7a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('dmc_reference_column')
        batch_op.drop_column('dmc_reference_sheet')
        batch_op.drop_column('dmc_reference_path')


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dmc_reference_path', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('dmc_reference_sheet', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('dmc_reference_column', sa.String(length=255), nullable=True))
