"""Add explicit working format and original-file traceability."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_working_format_and_original"
down_revision: str | None = "0014_backfill_source_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("working_format", sa.String(length=10), nullable=False, server_default="pdf"),
    )
    op.add_column("documents", sa.Column("original_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "documents",
        sa.Column("original_storage_path", sa.String(length=1000), nullable=True),
    )
    op.execute("UPDATE documents SET working_format = source_format")


def downgrade() -> None:
    op.drop_column("documents", "original_storage_path")
    op.drop_column("documents", "original_sha256")
    op.drop_column("documents", "working_format")