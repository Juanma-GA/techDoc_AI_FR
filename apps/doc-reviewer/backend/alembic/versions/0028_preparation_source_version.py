"""Track the document version used by preparation state."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028_preparation_source_version"
down_revision: str | None = "0027_preparation_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_preparations",
        sa.Column("source_version", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_preparations", "source_version")
