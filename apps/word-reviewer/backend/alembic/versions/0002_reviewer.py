"""reviewer schema - standards, batches, documents, runs, suggestions, rules, history.

Revision ID: 0002_reviewer
Revises: 0001_initial
Create Date: 2026-06-12 00:00:00.000000

Types portables SQLite <-> Postgres (sa.Uuid / sa.Boolean / sa.Text), pas de
SQL specifique. `app_config` est deja cree par 0001_initial.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_reviewer"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "standards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("builtin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_standards_code", "standards", ["code"], unique=True)

    op.create_table(
        "standard_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "standard_id",
            sa.Uuid(),
            sa.ForeignKey("standards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("builtin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("catalog_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("disabled_rule_codes", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("standard_id", "label", name="uq_standard_version"),
    )
    op.create_index(
        "ix_standard_versions_standard_id", "standard_versions", ["standard_id"]
    )

    op.create_table(
        "batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("label", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_dir", sa.String(1000), nullable=False),
        sa.Column("block_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "batch_id",
            sa.Uuid(),
            sa.ForeignKey("batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "standard_version_id",
            sa.Uuid(),
            sa.ForeignKey("standard_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("standard_version_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_sha256", "documents", ["sha256"])
    op.create_index("ix_documents_batch_id", "documents", ["batch_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False, server_default=""),
        sa.Column("replacement", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_zone", sa.String(40), nullable=False, server_default=""),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "standard_version_id",
            sa.Uuid(),
            sa.ForeignKey("standard_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rules_standard_version_id", "rules", ["standard_version_id"])

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("standard_version_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("summary", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_analysis_runs_document_id", "analysis_runs", ["document_id"])

    op.create_table(
        "suggestions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "rule_id",
            sa.Uuid(),
            sa.ForeignKey("rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rule_kind", sa.String(20), nullable=False),
        sa.Column("rule_code", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("proposed_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_id", sa.String(40), nullable=False, server_default=""),
        sa.Column("block_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("zone", sa.String(20), nullable=False, server_default="body"),
        sa.Column("semantic_zone", sa.String(40), nullable=False, server_default=""),
        sa.Column("char_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("char_end", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("span_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("feedback_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_suggestions_document_id", "suggestions", ["document_id"])
    op.create_index("ix_suggestions_run_id", "suggestions", ["run_id"])
    op.create_index("ix_suggestions_rule_id", "suggestions", ["rule_id"])
    op.create_index("ix_suggestions_rule_kind", "suggestions", ["rule_kind"])
    op.create_index("ix_suggestions_status", "suggestions", ["status"])

    op.create_table(
        "edit_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "suggestion_id",
            sa.Uuid(),
            sa.ForeignKey("suggestions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("version_before", sa.Integer(), nullable=False),
        sa.Column("version_after", sa.Integer(), nullable=False),
        sa.Column("snapshot_path", sa.String(1000), nullable=False),
        sa.Column("diff_summary", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rolled_back", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_index("ix_edit_history_document_id", "edit_history", ["document_id"])
    op.create_index("ix_edit_history_suggestion_id", "edit_history", ["suggestion_id"])


def downgrade() -> None:
    op.drop_table("edit_history")
    op.drop_table("suggestions")
    op.drop_table("analysis_runs")
    op.drop_table("rules")
    op.drop_table("documents")
    op.drop_table("batches")
    op.drop_table("standard_versions")
    op.drop_table("standards")
