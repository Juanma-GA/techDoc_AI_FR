"""S7 — drop XML-only built-in standards (S1000D, ATA iSpec 2200, S2000M).

Le Doc Reviewer analyse le rendu PDF publié, pas la source XML/SGML. Les
catalogues S1000D, ATA2200 et S2000M vérifiaient majoritairement des
champs/codes structurels (DMC, NSN, CAGE, Information Code, SMR, QPA…) qui
n'existent que dans la source et n'ont pas de sens sur un PDF. On retire ces
trois normes built-in (et leurs versions) du catalogue. Les normes textuelles
restent : ASD-STE100, MAT10000, ATA100.

Toute version personnalisée (builtin = 0) est préservée. Les FK
`documents.standard_version_id` / `rules.standard_version_id` /
`analysis_runs.standard_version_id` sont remises à NULL explicitement (SQLite
n'applique pas toujours ON DELETE SET NULL en migration). Les colonnes JSON
multi-normes (`standard_version_ids`) ne sont pas nettoyées : un ID orphelin
n'est simplement plus résolu au runtime (aucune règle émise).

Note : les règles de style rédactionnel S1000D/STE conservées vivent dans le
moteur transverse `app.checks.s1000d_checks` (toujours actif, indépendant du
catalogue) — elles ne sont pas concernées par cette suppression.

Revision ID: 0008_drop_xml_only_standards
Revises: 0007_phrase_level_caps_rule
Create Date: 2026-06-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0008_drop_xml_only_standards"
down_revision: str | None = "0007_phrase_level_caps_rule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_REMOVED_CODES = ("S1000D", "ATA2200", "S2000M")


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Collect the built-in version IDs about to be removed.
    rows = bind.execute(
        sa.text(
            "SELECT sv.id FROM standard_versions sv "
            "JOIN standards s ON s.id = sv.standard_id "
            "WHERE s.builtin = 1 AND s.code IN ('S1000D', 'ATA2200', 'S2000M')"
        )
    ).fetchall()
    version_ids = [r[0] for r in rows]

    # 2. Detach references so no row points at a soon-to-be-deleted version
    #    (SQLite ne déclenche pas toujours ON DELETE SET NULL en migration).
    if version_ids:
        for table in ("documents", "rules", "analysis_runs"):
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET standard_version_id = NULL "
                    "WHERE standard_version_id IN :ids"
                ).bindparams(sa.bindparam("ids", expanding=True)),
                {"ids": version_ids},
            )

    # 3. Delete the versions then the standards (built-in rows only).
    bind.execute(
        sa.text(
            "DELETE FROM standard_versions WHERE builtin = 1 AND standard_id IN "
            "(SELECT id FROM standards WHERE builtin = 1 AND code IN "
            "('S1000D', 'ATA2200', 'S2000M'))"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM standards WHERE builtin = 1 AND code IN "
            "('S1000D', 'ATA2200', 'S2000M')"
        )
    )


def downgrade() -> None:
    """Re-seed the three removed built-in standards from Python source.

    Best-effort : si l'import des catalogues échoue (ils ont été supprimés du
    code en même temps que cette migration), le downgrade est un no-op — les
    normes ne peuvent pas être recréées sans leur catalogue source.
    """
    try:
        import json
        import uuid
        from datetime import datetime, timezone

        from app.checks.standards import BUILTIN_STANDARDS
    except Exception:  # noqa: BLE001
        return

    by_code = {s["code"]: s for s in BUILTIN_STANDARDS}
    specs = [by_code[c] for c in _REMOVED_CODES if c in by_code]
    if not specs:
        return

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    for spec in specs:
        std_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO standards "
                "(id, code, label, description, builtin, created_at, updated_at) "
                "VALUES (:id, :code, :label, :desc, 1, :now, :now)"
            ),
            {
                "id": std_id,
                "code": spec["code"],
                "label": spec["label"],
                "desc": spec.get("description"),
                "now": now,
            },
        )
        for label, rules in spec["versions"].items():
            bind.execute(
                sa.text(
                    "INSERT INTO standard_versions "
                    "(id, standard_id, label, builtin, catalog_json, "
                    "created_at, updated_at) "
                    "VALUES (:id, :sid, :label, 1, :catalog, :now, :now)"
                ),
                {
                    "id": uuid.uuid4(),
                    "sid": std_id,
                    "label": label,
                    "catalog": json.dumps(
                        [r.as_dict() for r in rules], ensure_ascii=False
                    ),
                    "now": now,
                },
            )
