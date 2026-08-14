"""dmrl / cir / brex client rules columns on documents.

Revision ID: 0005_dmrl_cir
Revises: 0004_wizard_undo
Create Date: 2026-08-14 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_dmrl_cir"
down_revision: str | None = "0004_wizard_undo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("dmrl_json", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("cir_path", sa.String(length=1000), nullable=True))
    op.add_column("documents", sa.Column("brex_rules_path", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "brex_rules_path")
    op.drop_column("documents", "cir_path")
    op.drop_column("documents", "dmrl_json")
