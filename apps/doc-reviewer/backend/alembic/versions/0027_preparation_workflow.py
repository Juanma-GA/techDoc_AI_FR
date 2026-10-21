"""Persist per-document preparation and THALES preparation checklist."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_preparation_workflow"
down_revision: str | None = "0026_demo_document_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_preparations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("reference_filename", sa.String(length=500), nullable=False),
        sa.Column("reference_sha256", sa.String(length=64), nullable=False),
        sa.Column("reference_page_count", sa.Integer(), nullable=False),
        sa.Column("page_metadata_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("ocr_results_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("validated_pages_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("selected_provider", sa.String(length=40), nullable=True),
        sa.Column("page_decisions_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index(
        "ix_document_preparations_document_id",
        "document_preparations",
        ["document_id"],
        unique=True,
    )
    op.create_table(
        "preparation_checklists",
        sa.Column("client_code", sa.String(length=80), nullable=False),
        sa.Column("source_filename", sa.String(length=500), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("client_code"),
    )


def downgrade() -> None:
    op.drop_table("preparation_checklists")
    op.drop_index(
        "ix_document_preparations_document_id",
        table_name="document_preparations",
    )
    op.drop_table("document_preparations")
