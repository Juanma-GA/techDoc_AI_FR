"""Remove the three legacy demo custom rules."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0021_remove_default_custom_rules"
down_revision: str | None = "0014_pnr_mapping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM rules "
            "WHERE name IN (:space_rule, :caps_rule, :accent_rule)"
        ),
        {
            "space_rule": "Pas d'oubli d'espace après ponctuation",
            "caps_rule": "Pas de mot en MAJUSCULES",
            "accent_rule": "Pas d'oubli d'accent (mots FR fréquents)",
        },
    )


def downgrade() -> None:
    pass