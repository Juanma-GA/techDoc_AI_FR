"""Add the mandatory manufacturer field to the document mapping."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0023_manufacturer_mapping"
down_revision: str | None = "0022_last_issue_date_mapping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "meta_manufacturer",
            sa.String(length=20),
            nullable=False,
            server_default="Airbus",
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "meta_manufacturer")