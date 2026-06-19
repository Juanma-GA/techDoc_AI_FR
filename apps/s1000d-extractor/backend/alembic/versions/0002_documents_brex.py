"""documents + brex_profiles.

Revision ID: 0002_documents_brex
Revises: 0001_initial
Create Date: 2026-06-10 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_documents_brex"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brex_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("s1000d_issue", sa.String(length=10), nullable=False),
        sa.Column("xml_path", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("source_format", sa.String(length=10), nullable=False),
        sa.Column("s1000d_issue", sa.String(length=10), nullable=False),
        sa.Column("context_hint", sa.String(length=20), nullable=False),
        sa.Column("brex_id", sa.String(length=36), nullable=True),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("xml_path", sa.String(length=1000), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("dm_type", sa.String(length=20), nullable=True),
        sa.Column("ir_json", sa.Text(), nullable=True),
        sa.Column("violations_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["brex_id"], ["brex_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_status", "documents", ["status"])


def downgrade() -> None:
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_table("documents")
    op.drop_table("brex_profiles")