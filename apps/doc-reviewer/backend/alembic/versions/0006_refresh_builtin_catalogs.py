"""S5 — refresh built-in catalogs after step_pattern regex fix.

The step_pattern verb regex previously had a too-permissive English
alternative `[A-Z][a-z]+e?(?:\\s|$)` that matched any capitalised
short token followed by space — so « Le panneau est retiré. » was
incorrectly considered to start with a verb. The regex now requires
≥ 4 lowercase chars in the English alternative, and a word-boundary
after the French infinitive suffix.

This migration re-imports every built-in catalog from Python source
and writes it back to the `catalog_json` column. Custom standards are
untouched. Idempotent: re-running it just overwrites with the same
values when the Python source hasn't moved.

Revision ID: 0006_refresh_builtin_catalogs
Revises: 0005_rule_toggle_per_version
Create Date: 2026-05-11
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision: str = "0006_refresh_builtin_catalogs"
down_revision: str | None = "0005_rule_toggle_per_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    try:
        from app.checks.standards import BUILTIN_STANDARDS
    except Exception:  # noqa: BLE001
        return

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    for spec in BUILTIN_STANDARDS:
        std_row = bind.execute(
            sa.text("SELECT id FROM standards WHERE code = :code AND builtin = 1"),
            {"code": spec["code"]},
        ).first()
        if std_row is None:
            continue
        for label, rules in spec["versions"].items():
            payload = json.dumps([r.as_dict() for r in rules], ensure_ascii=False)
            bind.execute(
                sa.text(
                    "UPDATE standard_versions SET catalog_json = :payload, "
                    "updated_at = :now WHERE standard_id = :sid "
                    "AND label = :label AND builtin = 1"
                ),
                {"payload": payload, "now": now, "sid": std_row[0], "label": label},
            )


def downgrade() -> None:
    # No-op : the previous catalog_json is functionally equivalent
    # (same rule codes, just with a buggier regex). Re-running upgrade
    # is the way to roll forward.
    pass
