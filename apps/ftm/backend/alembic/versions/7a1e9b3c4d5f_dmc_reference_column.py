"""dmc_reference_column

Revision ID: 7a1e9b3c4d5f
Revises: 4cff136be3c3
Create Date: 2026-04-30 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '7a1e9b3c4d5f'
down_revision: str | None = '4cff136be3c3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dmc_reference_sheet', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('dmc_reference_column', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('dmc_reference_column')
        batch_op.drop_column('dmc_reference_sheet')
