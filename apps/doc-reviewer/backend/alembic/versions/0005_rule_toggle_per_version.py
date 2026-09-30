"""S4 — per-version rule toggle (built-in catalog rules can be disabled).

Adds `StandardVersion.disabled_rule_codes` (JSON list of rule code strings).
At runtime, the engine filters the catalog through this set so the user
can disable individual built-in rules without modifying the catalog
itself (which stays read-only for built-in standards).

Also refreshes every built-in version's `catalog_json` with the new
S1000D rules (S1000D_APPLICABILITY, S1000D_DM_TITLE, S1000D_FIGURE_CAPTION)
that were added in this revision.

Revision ID: 0005_rule_toggle_per_version
Revises: 0004_ste100_and_multi_norms
Create Date: 2026-05-11
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision: str = "0005_rule_toggle_per_version"
down_revision: str | None = "0004_ste100_and_multi_norms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("standard_versions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "disabled_rule_codes",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
    _refresh_builtin_catalogs()


def downgrade() -> None:
    with op.batch_alter_table("standard_versions") as batch_op:
        batch_op.drop_column("disabled_rule_codes")


def _refresh_builtin_catalogs() -> None:
    """Update each built-in standard_version's catalog_json with the latest
    catalog from Python source. Built-in rows only; custom versions are
    untouched."""
    try:
        from app.checks.standards import BUILTIN_STANDARDS, serialize_builtin_version
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
            payload = json.dumps(serialize_builtin_version(spec, label), ensure_ascii=False)
            bind.execute(
                sa.text(
                    "UPDATE standard_versions SET catalog_json = :payload, "
                    "updated_at = :now WHERE standard_id = :sid "
                    "AND label = :label AND builtin = 1"
                ),
                {"payload": payload, "now": now, "sid": std_row[0], "label": label},
            )
