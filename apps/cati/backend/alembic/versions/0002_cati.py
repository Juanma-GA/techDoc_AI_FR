"""cati tables - documents (PDF uploades) + items (nomenclature extraite).

Revision ID: 0002_cati
Revises: 0001_initial
Create Date: 2026-07-07 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_cati"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cati_document",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=120), server_default="", nullable=False),
        sa.Column("size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("page_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("extraction_method", sa.String(length=16), server_default="deterministic", nullable=False),
        sa.Column("header_meta", sa.Text(), server_default="{}", nullable=False),
        sa.Column("extraction_meta", sa.Text(), server_default="{}", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256", name="uq_cati_document_sha256"),
    )
    op.create_index("ix_cati_document_sha256", "cati_document", ["sha256"], unique=False)

    op.create_table(
        "cati_item",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("fields", sa.Text(), server_default="{}", nullable=False),
        sa.Column("included", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("edited", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["cati_document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cati_item_document_id", "cati_item", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cati_item_document_id", table_name="cati_item")
    op.drop_table("cati_item")
    op.drop_index("ix_cati_document_sha256", table_name="cati_document")
    op.drop_table("cati_document")
