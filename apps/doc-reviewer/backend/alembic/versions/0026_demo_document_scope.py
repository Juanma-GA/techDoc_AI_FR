"""Scope uploaded documents to normal or demo mode."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026_demo_document_scope"
down_revision: str | None = "0025_default_ste100_rules_disabled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index("ix_documents_is_demo", "documents", ["is_demo"])
    documents = sa.table(
        "documents",
        sa.column("original_filename", sa.String()),
        sa.column("is_demo", sa.Boolean()),
    )
    op.execute(
        documents.update()
        .where(
            sa.func.lower(documents.c.original_filename).in_(
                ("demo_cmm_pdf.pdf", "demo_cmm_pdf_anonyme.pdf")
            )
        )
        .values(is_demo=sa.true())
    )


def downgrade() -> None:
    op.drop_index("ix_documents_is_demo", table_name="documents")
    op.drop_column("documents", "is_demo")
