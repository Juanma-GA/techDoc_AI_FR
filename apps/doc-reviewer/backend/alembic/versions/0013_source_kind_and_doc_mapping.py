"""Source de la regle sur les anomalies + mapping manuel par document.

- `suggestions.source_kind` : provenance affichee/filtrable dans la liste des
  anomalies ("norme" | "checklist" | "regle" | "transverse"). Calculee par
  `rules_engine.classify_source` a la materialisation.
- `documents.meta_revision_date` / `meta_cmm_number` / `meta_first_issue_date`
  / `meta_revision_number` : mapping manuel par document, reference par les
  consignes de checklist lors du scan IA.

Compatible SQLite ET Postgres (lignes existantes -> "norme" / NULL).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_source_kind_and_doc_mapping"
down_revision: str | None = "0012_docx_native_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "suggestions",
        sa.Column("source_kind", sa.String(length=20), nullable=False, server_default="norme"),
    )
    op.create_index(
        "ix_suggestions_source_kind", "suggestions", ["source_kind"], unique=False
    )
    op.add_column("documents", sa.Column("meta_revision_date", sa.String(length=60), nullable=True))
    op.add_column("documents", sa.Column("meta_cmm_number", sa.String(length=120), nullable=True))
    op.add_column("documents", sa.Column("meta_first_issue_date", sa.String(length=60), nullable=True))
    op.add_column("documents", sa.Column("meta_revision_number", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "meta_revision_number")
    op.drop_column("documents", "meta_first_issue_date")
    op.drop_column("documents", "meta_cmm_number")
    op.drop_column("documents", "meta_revision_date")
    op.drop_index("ix_suggestions_source_kind", table_name="suggestions")
    op.drop_column("suggestions", "source_kind")
