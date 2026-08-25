"""dm_document_links + dm_versions tables for DMRL linking and DM versioning.

Revision ID: 0006_dm_versioning_links
Revises: 0005_dmrl_cir
Create Date: 2026-08-24 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_dm_versioning_links"
down_revision: str | None = "0005_dmrl_cir"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create dm_document_links table
    op.create_table(
        "dm_document_links",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("doc_id", sa.String(36), nullable=False),
        sa.Column("dmrl_line_id", sa.String(100), nullable=True),
        sa.Column("dm_code", sa.String(100), nullable=False),
        sa.Column("auto_linked", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dm_document_links_doc_id", "dm_document_links", ["doc_id"])
    op.create_index("ix_dm_document_links_dmrl_line_id", "dm_document_links", ["dmrl_line_id"])
    op.create_index("ix_dm_document_links_dm_code", "dm_document_links", ["dm_code"])

    # Create dm_versions table
    op.create_table(
        "dm_versions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("doc_id", sa.String(36), nullable=False),
        sa.Column("dm_code", sa.String(100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author", sa.String(100), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dm_versions_doc_id", "dm_versions", ["doc_id"])
    op.create_index("ix_dm_versions_dm_code", "dm_versions", ["dm_code"])


def downgrade() -> None:
    op.drop_table("dm_versions")
    op.drop_table("dm_document_links")
