"""S2 — standards & standard_versions tables + FKs + seed built-in.

Adds first-class multi-standard support to the reviewer: built-in
catalogs for S1000D 5.0/6.0, MAT10000 v1, S2000M issue 7, ATA100 rev 38,
ATA iSpec 2200 2018-1, plus nullable FKs on `documents`, `rules`,
`analysis_runs`. Existing documents are backfilled to S1000D 6.0 so the
analyse pipeline keeps a target norm post-migration.

Revision ID: 0003_standards_versioning
Revises: 0002_app_config
Create Date: 2026-05-11
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision: str = "0003_standards_versioning"
down_revision: str | None = "0002_app_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "standards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True, index=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("builtin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "standard_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "standard_id",
            sa.Uuid(),
            sa.ForeignKey("standards.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("builtin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("catalog_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("standard_id", "label", name="uq_standard_version"),
    )

    # SQLite ne supporte pas ADD COLUMN FK via op.add_column direct ;
    # batch_alter_table reste compatible Postgres et SQLite.
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("standard_version_id", sa.Uuid(), nullable=True))
        batch_op.create_index(
            "ix_documents_standard_version_id", ["standard_version_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_documents_standard_version",
            "standard_versions",
            ["standard_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("rules") as batch_op:
        batch_op.add_column(sa.Column("standard_version_id", sa.Uuid(), nullable=True))
        batch_op.create_index(
            "ix_rules_standard_version_id", ["standard_version_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_rules_standard_version",
            "standard_versions",
            ["standard_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("analysis_runs") as batch_op:
        batch_op.add_column(sa.Column("standard_version_id", sa.Uuid(), nullable=True))
        batch_op.create_index(
            "ix_analysis_runs_standard_version_id",
            ["standard_version_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_runs_standard_version",
            "standard_versions",
            ["standard_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _seed_builtin_standards()


def downgrade() -> None:
    with op.batch_alter_table("analysis_runs") as batch_op:
        batch_op.drop_constraint("fk_runs_standard_version", type_="foreignkey")
        batch_op.drop_index("ix_analysis_runs_standard_version_id")
        batch_op.drop_column("standard_version_id")

    with op.batch_alter_table("rules") as batch_op:
        batch_op.drop_constraint("fk_rules_standard_version", type_="foreignkey")
        batch_op.drop_index("ix_rules_standard_version_id")
        batch_op.drop_column("standard_version_id")

    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_standard_version", type_="foreignkey")
        batch_op.drop_index("ix_documents_standard_version_id")
        batch_op.drop_column("standard_version_id")

    op.drop_table("standard_versions")
    op.drop_table("standards")


def _seed_builtin_standards() -> None:
    """Insère les 5 normes built-in + leurs versions et catalogues.

    L'import se fait à l'intérieur de la migration pour rester
    autonome ; en cas d'erreur d'import (ex : test isolé), la migration
    n'échoue pas — la table reste vide et le bootstrap applicatif
    (re-seed) prendra le relais.
    """
    try:
        from app.checks.standards import BUILTIN_STANDARDS, serialize_builtin_version
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

    default_doc_version_id: uuid.UUID | None = None
    for spec in BUILTIN_STANDARDS:
        std_id = uuid.uuid4()
        bind.execute(
            std_table.insert().values(
                id=std_id,
                code=spec["code"],
                label=spec["label"],
                description=spec.get("description"),
                builtin=True,
                created_at=now,
                updated_at=now,
            )
        )
        versions: dict[str, list] = spec["versions"]  # type: ignore[assignment]
        for label, rules in versions.items():
            ver_id = uuid.uuid4()
            catalog_payload = serialize_builtin_version(spec, label)
            bind.execute(
                ver_table.insert().values(
                    id=ver_id,
                    standard_id=std_id,
                    label=label,
                    builtin=True,
                    catalog_json=json.dumps(catalog_payload, ensure_ascii=False),
                    created_at=now,
                    updated_at=now,
                )
            )
            if spec["code"] == "S1000D" and label == "6.0":
                default_doc_version_id = ver_id

    if default_doc_version_id is not None:
        docs_table = sa.table(
            "documents",
            sa.column("standard_version_id", sa.Uuid()),
        )
        bind.execute(
            docs_table.update()
            .where(docs_table.c.standard_version_id.is_(None))
            .values(standard_version_id=default_doc_version_id)
        )
