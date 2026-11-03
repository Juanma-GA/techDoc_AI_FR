from __future__ import annotations

from pathlib import Path

import pytest

from app.api import catpart_diff as catpart_diff_api
from app.core import catpart_diff, catpart_names
from app.core.errors import AppError


def _write_catpart(root: Path, filename: str) -> None:
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic CATPart")


def test_catpart_folder_limit_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    monkeypatch.setattr(catpart_names, "MAX_CATPART_FILES_PER_FOLDER", 2)
    for index in range(3):
        _write_catpart(old_root, f"part-{index}.CATPart")

    with pytest.raises(AppError) as error:
        catpart_diff.compare_folders(old_root, new_root)

    assert error.value.code == "CATPART_LIMIT_EXCEEDED"


def test_api_rejects_folder_outside_input_root(
    client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "input"
    outside = tmp_path / "outside"
    (input_root / "old").mkdir(parents=True)
    outside.mkdir()
    monkeypatch.setattr(
        catpart_diff_api.onedrive,
        "root_for_scope",
        lambda db, scope: str(input_root),
    )

    response = client.post(
        "/api/v1/diff/catparts",
        json={"old_path": str(input_root / "old"), "new_path": str(outside)},
    )

    assert response.status_code == 400


def test_api_returns_ge_files_with_same_sin_and_different_pns(
    client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "input"
    old_root = input_root / "old"
    new_root = input_root / "new"
    old_root.mkdir(parents=True)
    new_root.mkdir(parents=True)
    old_file = "GE_050N9_9994M99P01_SEAL.CATPart"
    new_file = "GE_050N9_8888M88P02_WIRE.CATPart"
    _write_catpart(old_root, old_file)
    _write_catpart(new_root, new_file)
    monkeypatch.setattr(
        catpart_diff_api.onedrive,
        "root_for_scope",
        lambda db, scope: str(input_root),
    )

    response = client.post(
        "/api/v1/diff/catparts",
        json={"old_path": str(old_root), "new_path": str(new_root)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["matches"] == [
        {
            "sin": "050N9",
            "old_pns": ["9994M99P01"],
            "new_pns": ["8888M88P02"],
            "old_files": [old_file],
            "new_files": [new_file],
        }
    ]
