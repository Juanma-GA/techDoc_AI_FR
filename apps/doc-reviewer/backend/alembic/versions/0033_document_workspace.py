"""Track the workspace (control / preparation) a document was imported into."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0033_document_workspace"
down_revision: str | None = "0032_preparation_absent_page_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("workspace", sa.String(20), server_default="control", nullable=False),
    )
    op.create_index("ix_documents_workspace", "documents", ["workspace"])
    # Existing documents opened in the preparation workspace have a
    # preparation record: classify them as preparation documents.
    op.execute(
        "UPDATE documents SET workspace = 'preparation' "
        "WHERE id IN (SELECT document_id FROM document_preparations)"
    )


def downgrade() -> None:
    op.drop_index("ix_documents_workspace", table_name="documents")
    op.drop_column("documents", "workspace")
