"""Add the optional PNR document mapping field."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0014_pnr_mapping"
down_revision: str | None = "0020_rename_atex_custom_standard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("meta_pnr_number", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "meta_pnr_number")