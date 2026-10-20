"""Store the unique material slot used for mono-body colorization.

Revision ID: 0010_nomenclature_mono_texture
Revises: 0009_nomenclature_optimized
Create Date: 2026-10-12 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0010_nomenclature_mono_texture"
down_revision: str | None = "0009_nomenclature_optimized"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nomenclature_items",
        sa.Column("mono_texture", sa.String(length=200), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("nomenclature_items", "mono_texture")