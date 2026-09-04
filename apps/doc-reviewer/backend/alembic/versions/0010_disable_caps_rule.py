"""Desactive la regle seedee « Pas de mot en MAJUSCULES » (case_capitalize).

Sur des documents techniques (aeronautique), l'usage des majuscules est
massivement legitime (WARNING/CAUTION/NOTE, titres de section, acronymes,
references) : la regle produisait trop de faux positifs. On la desactive
(sans la supprimer : elle reste visible et re-activable dans l'onglet Regles).

Ne touche que les regles ENCORE activees, pour ne pas ecraser un choix
utilisateur qui l'aurait deja desactivee/reactivee sciemment... on ne peut pas
distinguer, donc on ne desactive que si enabled=1 (idempotent au re-run).

Compatible SQLite ET Postgres.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0010_disable_caps_rule"
down_revision: str | None = "0009_suggestion_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().execute(
        text("UPDATE rules SET enabled = 0 WHERE kind = 'case_capitalize' AND enabled = 1")
    )


def downgrade() -> None:
    op.get_bind().execute(
        text("UPDATE rules SET enabled = 1 WHERE kind = 'case_capitalize' AND enabled = 0")
    )
