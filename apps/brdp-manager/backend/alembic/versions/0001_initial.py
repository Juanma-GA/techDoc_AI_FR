"""initial schema - app_config, project_config, brdps, notes.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-24 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_config",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), server_default="", nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "project_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(length=200), server_default="", nullable=False),
        sa.Column("model_ident_code", sa.String(length=20), server_default="", nullable=False),
        sa.Column("system_diff_code", sa.String(length=4), server_default="A", nullable=False),
        sa.Column("issue_number", sa.String(length=10), server_default="001", nullable=False),
        sa.Column("in_work", sa.String(length=10), server_default="00", nullable=False),
        sa.Column("language_iso", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("country_iso", sa.String(length=10), server_default="US", nullable=False),
        sa.Column(
            "security_classification", sa.String(length=10), server_default="01", nullable=False
        ),
        sa.Column("enterprise_code", sa.String(length=20), server_default="", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "brdps",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("title", sa.Text(), server_default="", nullable=False),
        sa.Column("definition", sa.Text(), server_default="", nullable=False),
        sa.Column("proposal", sa.Text(), server_default="", nullable=False),
        sa.Column("validation", sa.String(length=20), server_default="Pending", nullable=False),
        sa.Column("comments", sa.Text(), server_default="", nullable=False),
        sa.Column("history", sa.Text(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "notes",
        sa.Column("brdp_id", sa.String(length=100), nullable=False),
        sa.Column("text", sa.Text(), server_default="", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["brdp_id"], ["brdps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("brdp_id"),
    )


def downgrade() -> None:
    op.drop_table("notes")
    op.drop_table("brdps")
    op.drop_table("project_config")
    op.drop_table("app_config")
