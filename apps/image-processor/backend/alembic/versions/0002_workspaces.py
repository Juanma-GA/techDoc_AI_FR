"""Persist startup Excel preferences and complete image histories."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_workspaces"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "excel_preset",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("state", sa.Text(), nullable=False),
    )
    op.create_table(
        "image_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("piece_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("operation_count", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
    )
    op.create_index("ix_image_history_updated_at", "image_history", ["updated_at"])
    op.create_table(
        "file_asset",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(150), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.UniqueConstraint("owner_id", "sha256", "name"),
    )
    op.create_index("ix_file_asset_owner_id", "file_asset", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_file_asset_owner_id", table_name="file_asset")
    op.drop_table("file_asset")
    op.drop_index("ix_image_history_updated_at", table_name="image_history")
    op.drop_table("image_history")
    op.drop_table("excel_preset")
