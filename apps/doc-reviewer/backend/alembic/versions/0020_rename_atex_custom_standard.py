"""Rename the local custom standard to its owning company code."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0020_rename_atex_custom_standard"
down_revision: str | None = "0019_compiled_builtin_catalogs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE standards SET code = :new_code "
            "WHERE code = :old_code "
            "AND NOT EXISTS (SELECT 1 FROM standards WHERE code = :new_code)"
        ),
        {"old_code": "ATEXIS-CUSTOM", "new_code": "THALES-CUSTOM"},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE standards SET code = :old_code "
            "WHERE code = :new_code "
            "AND NOT EXISTS (SELECT 1 FROM standards WHERE code = :old_code)"
        ),
        {"old_code": "ATEXIS-CUSTOM", "new_code": "THALES-CUSTOM"},
    )