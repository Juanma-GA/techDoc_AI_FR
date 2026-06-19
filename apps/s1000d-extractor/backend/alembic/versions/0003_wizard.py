"""wizard state columns on documents.

Revision ID: 0003_wizard
Revises: 0002_documents_brex
Create Date: 2026-06-11 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_wizard"
down_revision: str | None = "0002_documents_brex"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("wizard_step", sa.String(length=20), nullable=True))
    op.add_column("documents", sa.Column("split_level", sa.String(length=20), nullable=True))
    op.add_column("documents", sa.Column("dms_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "dms_json")
    op.drop_column("documents", "split_level")
    op.drop_column("documents", "wizard_step")
