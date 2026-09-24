"""Add generic client metadata and backfill document context fields."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0024_client_metadata_json"
down_revision: str | None = "0023_manufacturer_mapping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_LEGACY_METADATA_FIELDS = (
    "meta_revision_date",
    "meta_cmm_number",
    "meta_first_issue_date",
    "meta_last_issue_date",
    "meta_revision_number",
    "meta_pnr_number",
    "meta_manufacturer",
    "document_language",
)


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "client_metadata_json",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
    )
    documents = sa.table(
        "documents",
        sa.column("id", sa.Uuid()),
        sa.column("client_metadata_json", sa.JSON()),
        *(sa.column(field, sa.String()) for field in _LEGACY_METADATA_FIELDS),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            documents.c.id,
            *(documents.c[field] for field in _LEGACY_METADATA_FIELDS),
        )
    ).mappings()
    for row in rows:
        connection.execute(
            documents.update()
            .where(documents.c.id == row["id"])
            .values(
                client_metadata_json={
                    field: row[field] for field in _LEGACY_METADATA_FIELDS
                }
            )
        )


def downgrade() -> None:
    op.drop_column("documents", "client_metadata_json")