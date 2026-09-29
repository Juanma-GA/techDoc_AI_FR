"""Fix ATA_CHAPTER_REF so valid references are not reported as violations."""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_fix_ata_chapter_ref"
down_revision: str | None = "0017_compiled_rule_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_PATTERN = r"\b\d{2}-\d{2}-\d{2}\b"
_NEW_PATTERN = (
    r"\b(?i:ATA|Chapter|Chapitre)\s+"
    r"(?!\d{2}-\d{2}-\d{2}\b)\d{1,3}(?:\s*[-./]\s*\d{1,3}){0,2}\b"
)


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT sv.id, sv.catalog_json
            FROM standard_versions AS sv
            JOIN standards AS s ON s.id = sv.standard_id
            WHERE s.code = :code AND sv.builtin = 1
            """
        ),
        {"code": "ATA100"},
    ).mappings()

    for row in rows:
        try:
            catalog = json.loads(row["catalog_json"] or "[]")
        except (TypeError, ValueError):
            continue
        changed = False
        for rule in catalog if isinstance(catalog, list) else []:
            if (
                isinstance(rule, dict)
                and rule.get("code") == "ATA_CHAPTER_REF"
                and rule.get("pattern") == _OLD_PATTERN
            ):
                rule.update(
                    {
                        "title": "Référence chapitre ATA mal formée",
                        "description": (
                            "Signale les références explicitement préfixées ATA, Chapter ou "
                            "Chapitre qui ne suivent pas le format chapitre-section-sujet "
                            "(ex : ATA 24-21-00)."
                        ),
                        "pattern": _NEW_PATTERN,
                        "message": "Référence ATA mal formée — utiliser le format CH-SE-SU.",
                    }
                )
                changed = True
        if changed:
            connection.execute(
                sa.text(
                    "UPDATE standard_versions SET catalog_json = :catalog WHERE id = :id"
                ),
                {
                    "id": row["id"],
                    "catalog": json.dumps(catalog, ensure_ascii=False),
                },
            )


def downgrade() -> None:
    # The old pattern flags valid ATA references and must not be restored.
    pass
