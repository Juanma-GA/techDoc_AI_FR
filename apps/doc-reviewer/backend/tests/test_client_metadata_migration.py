"""Migration coverage for generic document metadata backfill."""

from __future__ import annotations

import importlib.util
import json
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
        / "0024_client_metadata_json.py"
    )
    spec = importlib.util.spec_from_file_location("client_metadata_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_upgrade_backfills_legacy_document_fields_into_json() -> None:
    engine = sa.create_engine("sqlite://")
    document_id = uuid.uuid4()
    fields = {
        "meta_revision_date": "JUL 27/26",
        "meta_cmm_number": "79-30-02",
        "meta_first_issue_date": None,
        "meta_last_issue_date": None,
        "meta_revision_number": "Rev. 01",
        "meta_pnr_number": "1-879-SB",
        "meta_manufacturer": "Boeing",
        "document_language": "en",
    }
    expected = {**fields}

    with engine.begin() as connection:
        documents = sa.Table(
            "documents",
            sa.MetaData(),
            sa.Column("id", sa.Uuid(), primary_key=True),
            *(sa.Column(name, sa.String(120)) for name in fields),
        )
        documents.create(connection)
        connection.execute(documents.insert().values(id=document_id, **fields))

        with Operations.context(MigrationContext.configure(connection)):
            _load_migration().upgrade()

        stored = connection.exec_driver_sql(
            "SELECT client_metadata_json FROM documents WHERE id = ?",
            (document_id.hex,),
        ).scalar_one()

    assert json.loads(stored) == expected
    engine.dispose()