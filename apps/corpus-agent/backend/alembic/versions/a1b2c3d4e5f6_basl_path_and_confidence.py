"""basl_path_and_confidence

Revision ID: a1b2c3d4e5f6
Revises: 9c3d6e5f7a8b
Create Date: 2026-05-18 00:00:00.000000

Ajoute `projects.basl_path` (fichier BASL séparé du suivi ATM) et
`anomalies.confidence` (niveau de confiance : elevee | moyenne | faible).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '9c3d6e5f7a8b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('basl_path', sa.String(length=500), nullable=True))
    with op.batch_alter_table('anomalies', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'confidence', sa.String(length=20),
            nullable=False, server_default='elevee',
        ))


def downgrade() -> None:
    with op.batch_alter_table('anomalies', schema=None) as batch_op:
        batch_op.drop_column('confidence')
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('basl_path')
