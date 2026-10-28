"""Store required page types declared absent from the document in preparation."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0032_preparation_absent_page_types"
down_revision: str | None = "0031_preparation_page_classification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_preparations",
        sa.Column(
            "absent_page_types_json",
            sa.Text(),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("document_preparations", "absent_page_types_json")
