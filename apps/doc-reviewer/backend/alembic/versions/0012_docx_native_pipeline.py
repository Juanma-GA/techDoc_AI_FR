"""Pipeline Word natif (dual-mode) : colonnes de support.

- `documents.source_format` : "pdf" (defaut, pipeline PDF actuel) ou "docx"
  (pipeline Word natif : parse python-docx, edition run-level, sortie .docx).
- `suggestions.target_id` : identifiant de bloc docx ("dp<N>") pour localiser la
  correction dans le .docx ; NULL pour les suggestions PDF (bbox).

Compatible SQLite ET Postgres (lignes existantes -> "pdf" / NULL).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_docx_native_pipeline"
down_revision: str | None = "0011_quality_gate_and_ste_longsentence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("source_format", sa.String(length=10), nullable=False, server_default="pdf"),
    )
    op.add_column(
        "suggestions",
        sa.Column("target_id", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("suggestions", "target_id")
    op.drop_column("documents", "source_format")
