"""Store manual page type and document page corrections for preparation."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0031_preparation_page_classification"
down_revision: str | None = "0030_preparation_mapping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_preparations",
        sa.Column(
            "page_classification_json",
            sa.Text(),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("document_preparations", "page_classification_json")
