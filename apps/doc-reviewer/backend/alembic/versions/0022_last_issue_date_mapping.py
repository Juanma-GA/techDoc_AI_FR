"""Add the optional previous-revision date to the document mapping."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0022_last_issue_date_mapping"
down_revision: str | None = "0021_remove_default_custom_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("meta_last_issue_date", sa.String(length=60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "meta_last_issue_date")
