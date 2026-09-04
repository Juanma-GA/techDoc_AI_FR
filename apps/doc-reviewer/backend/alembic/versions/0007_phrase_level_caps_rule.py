"""S6 — upgrade « Pas de mot en MAJUSCULES » to phrase-level detection.

The historic seed rule matched each ALL-CAPS token of ≥ 4 letters in
isolation, so « PROCÉDURE DE MAINTENANCE » triggered two unrelated
suggestions (PROCÉDURE → Procédure, MAINTENANCE → Maintenance) and the
« DE » stopword stayed uppercase. The new pattern matches the whole
phrase and the proposer outputs proper French title case (lowercase
stopwords).

This migration updates the seeded rule's `pattern` and `message` in
place, but only if the user hasn't already customised it (we match the
old pattern exactly to avoid overwriting edits).

Revision ID: 0007_phrase_level_caps_rule
Revises: 0006_refresh_builtin_catalogs
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0007_phrase_level_caps_rule"
down_revision: str | None = "0006_refresh_builtin_catalogs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD_PATTERN = r"\b[A-ZÀ-Ÿ]{4,}\b"
_NEW_PATTERN = (
    r"\b[A-ZÀ-Ÿ]{4,}(?:\s+(?:DE|DU|DES|LA|LE|LES|ET|OU|AU|AUX|EN|À|À|"
    r"D'|L'|[A-ZÀ-Ÿ]{2,}))*\b"
)
_NEW_MESSAGE = (
    "Phrase en majuscules — préférer la casse titre "
    "(Reject pour les acronymes légitimes)."
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE rules SET pattern = :new_pattern, message = :new_message "
            "WHERE kind = 'case_capitalize' AND pattern = :old_pattern"
        ),
        {
            "new_pattern": _NEW_PATTERN,
            "new_message": _NEW_MESSAGE,
            "old_pattern": _OLD_PATTERN,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE rules SET pattern = :old_pattern "
            "WHERE kind = 'case_capitalize' AND pattern = :new_pattern"
        ),
        {"old_pattern": _OLD_PATTERN, "new_pattern": _NEW_PATTERN},
    )
