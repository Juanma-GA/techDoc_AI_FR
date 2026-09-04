"""Portail qualite (colonnes `documents`) + fix STE_LONG_SENTENCE.

1. Ajoute sur `documents` : `convert_engine` (moteur de normalisation :
   pdf / libreoffice / word), `text_coverage` (% de pages porteuses de texte)
   et `quality` (analyzable | degraded | unusable). Renseignes a l'upload par
   `core.quality_gate`. Lignes existantes -> defauts optimistes (pdf/100/
   analyzable : elles ont deja ete revues).

2. Corrige la regle STE_LONG_SENTENCE des catalogues ASD-STE100 : l'ancien
   `pattern="STE100_LONG_SENTENCE"` (kind regex_flag) etait une SENTINELLE qui,
   compilee comme regex, ne matchait jamais -> detection de phrases longues
   silencieusement inoperante. On bascule en kind `sentence_length` (detecteur
   dedie par comptage de mots, cf. `checks.style_checks`) avec seuil `20`.
   Idempotent : ne patche que les entrees encore porteuses de la sentinelle,
   pour ne pas ecraser une edition utilisateur.

Compatible SQLite ET Postgres.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0011_quality_gate_and_ste_longsentence"
down_revision: str | None = "0010_disable_caps_rule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SENTINEL = "STE100_LONG_SENTENCE"


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("convert_engine", sa.String(length=20), nullable=False, server_default="pdf"),
    )
    op.add_column(
        "documents",
        sa.Column("text_coverage", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "documents",
        sa.Column("quality", sa.String(length=20), nullable=False, server_default="analyzable"),
    )

    bind = op.get_bind()
    rows = bind.execute(
        text(
            "SELECT sv.id, sv.catalog_json FROM standard_versions sv "
            "JOIN standards s ON s.id = sv.standard_id WHERE s.code = 'ASD-STE100'"
        )
    ).fetchall()
    for sv_id, catalog_json in rows:
        try:
            catalog = json.loads(catalog_json or "[]")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(catalog, list):
            continue
        changed = False
        for rule in catalog:
            if not isinstance(rule, dict):
                continue
            if rule.get("code") == "STE_LONG_SENTENCE" and rule.get("pattern") == _SENTINEL:
                rule["kind"] = "sentence_length"
                rule["pattern"] = "20"
                changed = True
        if changed:
            bind.execute(
                text("UPDATE standard_versions SET catalog_json = :cat WHERE id = :id"),
                {"cat": json.dumps(catalog, ensure_ascii=False), "id": sv_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        text(
            "SELECT sv.id, sv.catalog_json FROM standard_versions sv "
            "JOIN standards s ON s.id = sv.standard_id WHERE s.code = 'ASD-STE100'"
        )
    ).fetchall()
    for sv_id, catalog_json in rows:
        try:
            catalog = json.loads(catalog_json or "[]")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(catalog, list):
            continue
        changed = False
        for rule in catalog:
            if not isinstance(rule, dict):
                continue
            if rule.get("code") == "STE_LONG_SENTENCE" and rule.get("kind") == "sentence_length":
                rule["kind"] = "regex_flag"
                rule["pattern"] = _SENTINEL
                changed = True
        if changed:
            bind.execute(
                text("UPDATE standard_versions SET catalog_json = :cat WHERE id = :id"),
                {"cat": json.dumps(catalog, ensure_ascii=False), "id": sv_id},
            )

    op.drop_column("documents", "quality")
    op.drop_column("documents", "text_coverage")
    op.drop_column("documents", "convert_engine")
