"""Store metadata mapping independently for preparation."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030_preparation_mapping"
down_revision: str | None = "0029_document_comparisons"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_preparations",
        sa.Column(
            "preparation_mapping_json",
            sa.Text(),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("document_preparations", "preparation_mapping_json")
