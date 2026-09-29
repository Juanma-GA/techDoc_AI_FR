"""Persist compiled-rule versions and reproducible analysis snapshots."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_compiled_rule_foundation"
down_revision: str | None = "0016_document_language_and_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "compiled_rule_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("source_ref", sa.String(length=500), nullable=True),
        sa.Column("compiled_json", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", "version", name="uq_compiled_rule_code_version"),
    )
    op.create_index("ix_compiled_rule_versions_code", "compiled_rule_versions", ["code"])
    op.create_index("ix_compiled_rule_versions_source", "compiled_rule_versions", ["source"])
    op.create_index(
        "ix_compiled_rule_versions_content_sha256",
        "compiled_rule_versions",
        ["content_sha256"],
    )
    op.create_index("ix_compiled_rule_versions_active", "compiled_rule_versions", ["active"])
    op.add_column(
        "analysis_runs",
        sa.Column("context_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("compiled_rules_snapshot_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_runs", "snapshot_sha256")
    op.drop_column("analysis_runs", "compiled_rules_snapshot_json")
    op.drop_column("analysis_runs", "context_snapshot_json")
    op.drop_index("ix_compiled_rule_versions_active", table_name="compiled_rule_versions")
    op.drop_index("ix_compiled_rule_versions_content_sha256", table_name="compiled_rule_versions")
    op.drop_index("ix_compiled_rule_versions_source", table_name="compiled_rule_versions")
    op.drop_index("ix_compiled_rule_versions_code", table_name="compiled_rule_versions")
    op.drop_table("compiled_rule_versions")