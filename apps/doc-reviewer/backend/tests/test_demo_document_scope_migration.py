from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0026_demo_document_scope.py"
    )
    spec = importlib.util.spec_from_file_location(
        "demo_document_scope_migration",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_upgrade_keeps_normal_documents_and_backfills_demo_assets() -> None:
    engine = sa.create_engine("sqlite://")
    normal_id = uuid.uuid4()
    old_demo_id = uuid.uuid4()
    current_demo_id = uuid.uuid4()

    with engine.begin() as connection:
        documents = sa.Table(
            "documents",
            sa.MetaData(),
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("original_filename", sa.String(500), nullable=False),
        )
        documents.create(connection)
        connection.execute(
            documents.insert(),
            [
                {"id": normal_id, "original_filename": "normal.pdf"},
                {"id": old_demo_id, "original_filename": "DEMO_CMM_PDF.pdf"},
                {
                    "id": current_demo_id,
                    "original_filename": "DEMO_CMM_PDF_anonyme.pdf",
                },
            ],
        )

        with Operations.context(MigrationContext.configure(connection)):
            _load_migration().upgrade()

        rows = connection.execute(
            sa.text("SELECT id, is_demo FROM documents")
        ).all()

    demo_flags = {str(row.id).replace("-", ""): row.is_demo for row in rows}
    assert not demo_flags[normal_id.hex]
    assert bool(demo_flags[old_demo_id.hex])
    assert bool(demo_flags[current_demo_id.hex])
    engine.dispose()
