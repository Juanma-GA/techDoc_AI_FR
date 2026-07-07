"""cati - colonne challenge (rapport de controle LLM) sur cati_document.

Revision ID: 0003_challenge
Revises: 0002_cati
Create Date: 2026-07-07 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_challenge"
down_revision: str | None = "0002_cati"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cati_document",
        sa.Column("challenge", sa.Text(), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("cati_document", "challenge")
