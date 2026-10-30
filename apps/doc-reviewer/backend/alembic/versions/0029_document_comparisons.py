"""Persist the separate PDF comparison library."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029_document_comparisons"
down_revision: str | None = "0028_preparation_source_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("reference_index", sa.Integer(), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("ai_summary_json", sa.Text(), nullable=True),
        sa.Column(
            "ai_status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "ai_summary_truncated",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_comparisons_created_at",
        "document_comparisons",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_comparisons_created_at", table_name="document_comparisons")
    op.drop_table("document_comparisons")
