"""All filesystem assertions are limited to the isolated synthetic fixture root."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.config import settings

BASE = "/api/v1/image-replace/history"


def files() -> list[Path]:
    return [path for path in Path(settings.storage_dir).glob("*/*") if path.is_file()]


def test_files_are_versioned_locally_and_deduplicated(workspace_client, workspace_state) -> None:
    history_id = str(uuid4())
    assert workspace_client.put(f"{BASE}/{history_id}", json=workspace_state).status_code == 200
    saved = files()
    assert len(saved) == 2
    for path in saved:
        assert path.parent.name == history_id
        assert UUID(path.name[:36]).version == 4
    assert workspace_client.put(f"{BASE}/{history_id}", json=workspace_state).status_code == 200
    assert files() == saved
    assert workspace_client.get(f"{BASE}/{history_id}").status_code == 200
    assert workspace_client.delete(f"{BASE}/{history_id}").status_code == 204
    assert files() == []


def test_missing_saved_file_is_an_explicit_error(workspace_client, workspace_state) -> None:
    history_id = str(uuid4())
    workspace_client.put(f"{BASE}/{history_id}", json=workspace_state)
    next(path for path in files() if path.suffix == ".png").unlink()
    response = workspace_client.get(f"{BASE}/{history_id}")
    assert response.status_code == 500
    assert response.json()["code"] == "SAVED_FILE_MISSING"


def test_saved_checksum_is_checked_on_restore(workspace_client, workspace_state) -> None:
    history_id = str(uuid4())
    workspace_client.put(f"{BASE}/{history_id}", json=workspace_state)
    image = next(path for path in files() if path.suffix == ".png")
    contents = bytearray(image.read_bytes())
    contents[-1] ^= 1
    image.write_bytes(contents)
    response = workspace_client.get(f"{BASE}/{history_id}")
    assert response.status_code == 500
    assert response.json()["code"] == "SAVED_FILE_CORRUPT"


def test_reset_deletes_all_saved_files(workspace_client, workspace_state, excel_preset) -> None:
    workspace_client.put("/api/v1/image-replace/workspace/excel", json=excel_preset)
    workspace_client.put(f"{BASE}/{uuid4()}", json=workspace_state)
    assert len(files()) == 3
    assert workspace_client.post("/api/v1/admin/reset/all").status_code == 200
    assert files() == []


def test_snapshots_store_references_not_file_payloads(workspace_client, workspace_state) -> None:
    from sqlalchemy import select

    from app.db.models import ImageHistory
    from app.db.session import get_db

    history_id = str(uuid4())
    workspace_client.put(f"{BASE}/{history_id}", json=workspace_state)
    override = workspace_client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        encoded = db.scalar(select(ImageHistory.state))
        assert "asset_id" in encoded
        assert "data_url" not in encoded
        assert "base64" not in encoded
    finally:
        generator.close()


def test_failed_file_save_rolls_back_new_files_and_metadata(
    workspace_client, workspace_state, monkeypatch,
) -> None:
    from app.core.errors import AppError
    from app.services import workspace_storage

    write = workspace_storage._write_file

    def fail_workbook(asset, contents):
        if asset.name.endswith(".xlsx"):
            raise AppError("STORAGE_WRITE_FAILED", "Synthetic full disk.", 500)
        write(asset, contents)

    monkeypatch.setattr(workspace_storage, "_write_file", fail_workbook)
    response = workspace_client.put(f"{BASE}/{uuid4()}", json=workspace_state)
    assert response.status_code == 500
    assert response.json()["code"] == "STORAGE_WRITE_FAILED"
    assert files() == []
    assert workspace_client.get(BASE).json()["items"] == []


def test_failed_database_commit_removes_new_file_versions(
    workspace_client, workspace_state, monkeypatch,
) -> None:
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    def fail_commit(self):
        raise SQLAlchemyError("Synthetic commit failure.")

    with monkeypatch.context() as context:
        context.setattr(Session, "commit", fail_commit)
        with pytest.raises(SQLAlchemyError, match="Synthetic commit failure"):
            workspace_client.put(f"{BASE}/{uuid4()}", json=workspace_state)
    assert files() == []
    assert workspace_client.get(BASE).json()["items"] == []
