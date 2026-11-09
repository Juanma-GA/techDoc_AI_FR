"""Add a distinct evidence field to anomalies.

Revision ID: d7e8f9a0b1c2
Revises: c1d2e3f4a5b6
Create Date: 2026-11-04 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("anomalies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("evidence", sa.Text(), server_default="", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("anomalies", schema=None) as batch_op:
        batch_op.drop_column("evidence")
