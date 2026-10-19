"""Store the X000 optimized marker on nomenclature items.

Revision ID: 0009_nomenclature_optimized
Revises: 0008_nomenclature_slots
Create Date: 2026-10-07 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_nomenclature_optimized"
down_revision: str | None = "0008_nomenclature_slots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "nomenclature_items",
        sa.Column("optimized", sa.Boolean(), server_default="0", nullable=False),
    )
    op.create_index("ix_nomenclature_items_optimized", "nomenclature_items", ["optimized"])


def downgrade() -> None:
    op.drop_index("ix_nomenclature_items_optimized", table_name="nomenclature_items")
    op.drop_column("nomenclature_items", "optimized")
