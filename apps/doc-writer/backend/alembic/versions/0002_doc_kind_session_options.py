"""Add Document.kind + Session.output_format/length/tone/template_doc_id/style_doc_id.

Revision ID: 0002_doc_kind_session_options
Revises: 0001_initial
Create Date: 2026-05-13 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_doc_kind_session_options"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "kind",
                sa.String(length=16),
                server_default="source",
                nullable=False,
            )
        )

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "output_format",
                sa.String(length=32),
                server_default="markdown",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "length",
                sa.String(length=16),
                server_default="medium",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "tone",
                sa.String(length=32),
                server_default="professional",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("template_doc_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("style_doc_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_sessions_template_doc",
            "documents",
            ["template_doc_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_sessions_style_doc",
            "documents",
            ["style_doc_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_sessions_style_doc", type_="foreignkey")
        batch_op.drop_constraint("fk_sessions_template_doc", type_="foreignkey")
        batch_op.drop_column("style_doc_id")
        batch_op.drop_column("template_doc_id")
        batch_op.drop_column("tone")
        batch_op.drop_column("length")
        batch_op.drop_column("output_format")

    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_column("kind")
