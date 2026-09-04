"""Ajoute la colonne `feedback` (motif libre de rejet) sur `suggestions`.

Alimente la memoire de rejet : une anomalie rejetee avec son motif n'est plus
re-signalee a l'analyse suivante (signature rule_code + original_text).

Compatible SQLite ET Postgres (server_default="" pour les lignes existantes).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_suggestion_feedback"
down_revision: str | None = "0008_drop_xml_only_standards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "suggestions",
        sa.Column("feedback", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("suggestions", "feedback")
