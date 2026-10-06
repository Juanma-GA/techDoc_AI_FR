"""Add explicit document language."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_document_language_and_context"
down_revision: str | None = "0015_working_format_and_original"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("document_language", sa.String(length=2), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "document_language")
