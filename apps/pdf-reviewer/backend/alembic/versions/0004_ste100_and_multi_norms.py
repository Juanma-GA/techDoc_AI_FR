"""S3 — seed ASD-STE100 standard + multi-norm columns on Document.

Two related changes:

1. Split ASD-STE100 (style) from S1000D (structure documentaire) — seed the
   STE100 built-in standard with its writing-style rules, and replace the
   S1000D 6.0 catalog with a smaller structure-only set + the new
   `S1000D_DMC_FORMAT` rule. Existing custom rules attached to S1000D 6.0
   stay where they are (the FK survives the catalog refresh).

2. Add `Document.standard_version_ids` and `AnalysisRun.standard_version_ids`
   JSON columns so a single document can target several normes at once.
   The historical `standard_version_id` columns are kept for backward
   compat (= the « primary » norm of a multi-norm set).

Revision ID: 0004_ste100_and_multi_norms
Revises: 0003_standards_versioning
Create Date: 2026-05-11
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision: str = "0004_ste100_and_multi_norms"
down_revision: str | None = "0003_standards_versioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "standard_version_ids",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )

    with op.batch_alter_table("analysis_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "standard_version_ids",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )

    _seed_ste100_and_refresh_s1000d()


def downgrade() -> None:
    with op.batch_alter_table("analysis_runs") as batch_op:
        batch_op.drop_column("standard_version_ids")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("standard_version_ids")
    # The STE100 standard rows are NOT removed on downgrade — they may have
    # custom rules attached. Drop them manually if needed.


def _seed_ste100_and_refresh_s1000d() -> None:
    """Insert ASD-STE100 (new) + refresh S1000D's catalog_json with the
    structure-only ruleset. Idempotent."""
    try:
        from app.checks.standards import BUILTIN_STANDARDS
    except Exception:  # noqa: BLE001
        return

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    std_table = sa.table(
        "standards",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("label", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("builtin", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    ver_table = sa.table(
        "standard_versions",
        sa.column("id", sa.Uuid()),
        sa.column("standard_id", sa.Uuid()),
        sa.column("label", sa.String()),
        sa.column("builtin", sa.Boolean()),
        sa.column("catalog_json", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    specs_by_code = {s["code"]: s for s in BUILTIN_STANDARDS}

    # 1. Insert ASD-STE100 if not present.
    ste_spec = specs_by_code.get("ASD-STE100")
    if ste_spec is not None:
        existing = bind.execute(
            sa.text("SELECT id FROM standards WHERE code = :code"),
            {"code": "ASD-STE100"},
        ).first()
        if existing is None:
            ste_std_id = uuid.uuid4()
            bind.execute(
                std_table.insert().values(
                    id=ste_std_id,
                    code=ste_spec["code"],
                    label=ste_spec["label"],
                    description=ste_spec.get("description"),
                    builtin=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            for label, rules in ste_spec["versions"].items():
                bind.execute(
                    ver_table.insert().values(
                        id=uuid.uuid4(),
                        standard_id=ste_std_id,
                        label=label,
                        builtin=True,
                        catalog_json=json.dumps(
                            [r.as_dict() for r in rules], ensure_ascii=False
                        ),
                        created_at=now,
                        updated_at=now,
                    )
                )

    # 2. Refresh S1000D's catalog_json (built-in versions only) so the new
    #    structure-only catalog replaces the legacy STE-heavy one.
    s1000d_spec = specs_by_code.get("S1000D")
    if s1000d_spec is not None:
        s1000d_id_row = bind.execute(
            sa.text("SELECT id FROM standards WHERE code = :code"),
            {"code": "S1000D"},
        ).first()
        if s1000d_id_row is not None:
            for label, rules in s1000d_spec["versions"].items():
                payload = json.dumps(
                    [r.as_dict() for r in rules], ensure_ascii=False
                )
                bind.execute(
                    sa.text(
                        "UPDATE standard_versions SET catalog_json = :payload, "
                        "updated_at = :now WHERE standard_id = :sid "
                        "AND label = :label AND builtin = 1"
                    ),
                    {
                        "payload": payload,
                        "now": now,
                        "sid": s1000d_id_row[0],
                        "label": label,
                    },
                )
