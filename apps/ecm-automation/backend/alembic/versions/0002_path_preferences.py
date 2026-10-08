"""Persist the last-used source, tracker, and output paths."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_path_preferences"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "path_preferences",
        sa.Column("id", sa.Integer(), server_default="1", nullable=False),
        sa.Column("source_path", sa.Text(), server_default="", nullable=False),
        sa.Column("tracker_path", sa.Text(), server_default="", nullable=False),
        sa.Column("output_path", sa.Text(), server_default="", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("path_preferences")