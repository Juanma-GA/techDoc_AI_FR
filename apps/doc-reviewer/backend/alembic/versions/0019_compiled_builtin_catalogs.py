"""Store built-in standards as the current CompiledRule contract."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0019_compiled_builtin_catalogs"
down_revision: str | None = "0018_fix_ata_chapter_ref"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.checks.standards import BUILTIN_STANDARDS, serialize_builtin_version

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    for spec in BUILTIN_STANDARDS:
        standard_id = bind.execute(
            sa.text(
                "SELECT id FROM standards WHERE code = :code AND builtin = 1"
            ),
            {"code": spec["code"]},
        ).scalar()
        if standard_id is None:
            continue
        for label in spec["versions"]:
            payload = json.dumps(
                serialize_builtin_version(spec, label),
                ensure_ascii=False,
            )
            bind.execute(
                sa.text(
                    "UPDATE standard_versions SET catalog_json = :catalog, "
                    "updated_at = :now WHERE standard_id = :standard_id "
                    "AND label = :label AND builtin = 1"
                ),
                {
                    "catalog": payload,
                    "now": now,
                    "standard_id": standard_id,
                    "label": label,
                },
            )


def downgrade() -> None:
    # The previous JSON shape is still readable by the compatibility loader;
    # restoring it would reintroduce the split execution path.
    pass
