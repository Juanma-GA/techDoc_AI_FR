"""tree optimizer schema - imports, nodes, runs, suggestions.

Revision ID: 0002_tree_optimizer
Revises: 0001_initial
Create Date: 2026-06-01 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_tree_optimizer"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "structure_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_mode", sa.String(length=16), nullable=False),
        sa.Column("root_label", sa.String(length=500), server_default="", nullable=False),
        sa.Column("source_ref", sa.Text(), server_default="", nullable=False),
        sa.Column("node_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metrics_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tree_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("rel_path", sa.String(length=1000), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("ext", sa.String(length=40), server_default="", nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("depth", sa.Integer(), server_default="0", nullable=False),
        sa.Column("size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mtime", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["import_id"], ["structure_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["tree_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tree_nodes_import_id", "tree_nodes", ["import_id"])
    op.create_index("ix_tree_nodes_parent_id", "tree_nodes", ["parent_id"])
    op.create_index("ix_tree_nodes_rel_path", "tree_nodes", ["rel_path"])

    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="running", nullable=False),
        sa.Column("config_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("summary", sa.Text(), server_default="{}", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["import_id"], ["structure_imports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_optimization_runs_import_id", "optimization_runs", ["import_id"])

    op.create_table(
        "suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("old_path", sa.String(length=1000), nullable=False),
        sa.Column("new_path", sa.String(length=1000), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), server_default="", nullable=False),
        sa.Column("confidence", sa.String(length=20), server_default="moyenne", nullable=False),
        sa.Column("source", sa.String(length=12), server_default="llm", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["optimization_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["tree_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suggestions_run_id", "suggestions", ["run_id"])
    op.create_index("ix_suggestions_node_id", "suggestions", ["node_id"])
    op.create_index("ix_suggestions_status", "suggestions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_suggestions_status", table_name="suggestions")
    op.drop_index("ix_suggestions_node_id", table_name="suggestions")
    op.drop_index("ix_suggestions_run_id", table_name="suggestions")
    op.drop_table("suggestions")
    op.drop_index("ix_optimization_runs_import_id", table_name="optimization_runs")
    op.drop_table("optimization_runs")
    op.drop_index("ix_tree_nodes_rel_path", table_name="tree_nodes")
    op.drop_index("ix_tree_nodes_parent_id", table_name="tree_nodes")
    op.drop_index("ix_tree_nodes_import_id", table_name="tree_nodes")
    op.drop_table("tree_nodes")
    op.drop_table("structure_imports")
