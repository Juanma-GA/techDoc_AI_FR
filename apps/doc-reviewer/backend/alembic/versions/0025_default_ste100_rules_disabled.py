"""Disable ASD-STE100 rule checks by default."""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0025_default_ste100_rules_disabled"
down_revision: str | None = "0024_client_metadata_json"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        text(
            "SELECT sv.id, sv.catalog_json, sv.disabled_rule_codes "
            "FROM standard_versions sv "
            "JOIN standards s ON s.id = sv.standard_id "
            "WHERE s.code = 'ASD-STE100'"
        )
    ).fetchall()

    for version_id, catalog_json, disabled_json in rows:
        catalog = json.loads(catalog_json or "[]")
        disabled_codes = json.loads(disabled_json or "[]")
        if not isinstance(catalog, list) or not isinstance(disabled_codes, list):
            raise ValueError("ASD-STE100 catalog and disabled codes must be JSON lists")

        catalog_codes = {
            rule["code"]
            for rule in catalog
            if isinstance(rule, dict) and isinstance(rule.get("code"), str)
        }
        updated_disabled_codes = sorted(
            catalog_codes | {str(code) for code in disabled_codes}
        )
        if updated_disabled_codes == sorted({str(code) for code in disabled_codes}):
            continue
        bind.execute(
            text(
                "UPDATE standard_versions SET disabled_rule_codes = :codes "
                "WHERE id = :version_id"
            ),
            {
                "codes": json.dumps(updated_disabled_codes, ensure_ascii=False),
                "version_id": version_id,
            },
        )


def downgrade() -> None:
    """Preserve rule statuses, which may have been changed since upgrade."""
