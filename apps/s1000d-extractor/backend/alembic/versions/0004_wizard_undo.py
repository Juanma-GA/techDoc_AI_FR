"""wizard undo history column on documents.

Revision ID: 0004_wizard_undo
Revises: 0003_wizard
Create Date: 2026-07-15 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_wizard_undo"
down_revision: str | None = "0003_wizard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("dms_history_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "dms_history_json")
