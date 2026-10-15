from __future__ import annotations

from pathlib import Path

import pytest

from app.api import catpart_diff as catpart_diff_api
from app.core import catpart_diff, catpart_geometry
from app.core.errors import AppError

_STEP = """ISO-10303-21;
DATA;
#1 = CARTESIAN_POINT('', (0., 0., 0.));
#2 = CARTESIAN_POINT('', (1., 0., 0.));
#3 = CARTESIAN_POINT('', (0., 1., 0.));
#4 = PLANE('', #3);
ENDSEC;
END-ISO-10303-21;
"""


def test_geometry_signature_ignores_translation_and_uniform_scale() -> None:
    transformed = _STEP.replace("(0., 0., 0.)", "(10., 20., 30.)")
    transformed = transformed.replace("(1., 0., 0.)", "(12., 20., 30.)")
    transformed = transformed.replace("(0., 1., 0.)", "(10., 22., 30.)")

    first = catpart_geometry.parse_step_signature(_STEP)
    second = catpart_geometry.parse_step_signature(transformed)

    assert first is not None and second is not None
    assert first.quality == "partial"
    assert catpart_geometry.geometry_similarity(first, second) == 100


def test_exact_hash_group_matches_renamed_catparts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    (old_root / "legacy.CATPart").write_bytes(b"same binary content")
    (new_root / "renamed.CATPart").write_bytes(b"same binary content")
    monkeypatch.setattr(catpart_diff, "resolve_cadmpeg", lambda: (None, None))

    result = catpart_diff.compare_folders(old_root, new_root)

    assert result["exact"]["groups"] == 1
    assert result["exact"]["old_files"] == 1
    assert result["exact"]["new_files"] == 1
    assert result["candidates"] == []
    assert result["geometry_status"] == "not_requested"


def test_exact_mode_lists_nonidentical_files_without_cadmpeg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    (old_root / "old-name.CATPart").write_bytes(b"old part")
    (new_root / "new-name.CATPart").write_bytes(b"new part")
    monkeypatch.setattr(
        catpart_diff,
        "resolve_cadmpeg",
        lambda: pytest.fail("CADMPEG must not run in exact-hash mode."),
    )

    result = catpart_diff.compare_folders(old_root, new_root)

    assert result["exact"]["groups"] == 0
    assert result["unmatched_old"] == ["old-name.CATPart"]
    assert result["unmatched_new"] == ["new-name.CATPart"]
    assert result["geometry_status"] == "not_requested"


def test_exact_hash_mode_handles_thousands_of_files(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    for index in range(1_000):
        content = f"synthetic-part-{index:04d}".encode()
        (old_root / f"old-{index:04d}.CATPart").write_bytes(content)
        (new_root / f"new-{index:04d}.CATPart").write_bytes(content)

    result = catpart_diff.compare_folders(old_root, new_root)

    assert result["old_count"] == 1_000
    assert result["new_count"] == 1_000
    assert result["exact"]["groups"] == 1_000
    assert result["exact"]["old_files"] == 1_000
    assert result["exact"]["new_files"] == 1_000
    assert result["unmatched_old"] == []
    assert result["unmatched_new"] == []


def test_exact_hash_mode_lists_thousands_of_nonidentical_files(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    for index in range(1_000):
        (old_root / f"old-{index:04d}.CATPart").write_bytes(f"old-part-{index:04d}".encode())
        (new_root / f"new-{index:04d}.CATPart").write_bytes(f"new-part-{index:04d}".encode())

    result = catpart_diff.compare_folders(old_root, new_root)

    assert result["exact"]["groups"] == 0
    assert len(result["unmatched_old"]) == 1_000
    assert len(result["unmatched_new"]) == 1_000
    assert result["geometry_status"] == "not_requested"


def test_partial_geometry_proposes_candidate_not_confirmed_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    (old_root / "old_label.CATPart").write_bytes(b"revision zero")
    (new_root / "new_label.CATPart").write_bytes(b"revision one")
    signature = catpart_geometry.parse_step_signature(_STEP)
    assert signature is not None
    monkeypatch.setattr(catpart_diff, "resolve_cadmpeg", lambda: ("cadmpeg", None))
    monkeypatch.setattr(
        catpart_diff,
        "extract_geometry_signature",
        lambda source, executable, output_dir, stem: (signature, None),
    )

    result = catpart_diff.compare_folders(old_root, new_root, include_geometry=True)

    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["old_file"] == "old_label.CATPart"
    assert candidate["new_file"] == "new_label.CATPart"
    assert candidate["confidence"] == "low"
    assert candidate["binary_equal"] is False


def test_catpart_folder_limit_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    monkeypatch.setattr(catpart_diff, "MAX_CATPART_FILES_PER_FOLDER", 2)
    for index in range(3):
        (old_root / f"part-{index}.CATPart").write_bytes(b"x")

    with pytest.raises(AppError) as error:
        catpart_diff.compare_folders(old_root, new_root)

    assert error.value.code == "CATPART_LIMIT_EXCEEDED"


def test_geometry_limit_keeps_exact_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    for index in range(2):
        (old_root / f"old-{index}.CATPart").write_bytes(f"old-{index}".encode())
        (new_root / f"new-{index}.CATPart").write_bytes(f"new-{index}".encode())
    monkeypatch.setattr(catpart_diff, "MAX_GEOMETRY_FILES_PER_FOLDER", 1)
    monkeypatch.setattr(
        catpart_diff,
        "resolve_cadmpeg",
        lambda: pytest.fail("CADMPEG must not run beyond the geometry suggestion limit."),
    )

    result = catpart_diff.compare_folders(old_root, new_root, include_geometry=True)

    assert result["geometry_status"] == "limit_exceeded"
    assert result["exact"]["groups"] == 0
    assert len(result["unmatched_old"]) == 2
    assert len(result["unmatched_new"]) == 2


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


def test_api_compares_exact_bytes_without_filename_matching(
    client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "input"
    old_root = input_root / "old"
    new_root = input_root / "new"
    old_root.mkdir(parents=True)
    new_root.mkdir(parents=True)
    (old_root / "before.CATPart").write_bytes(b"identical")
    (new_root / "after.CATPart").write_bytes(b"identical")
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
    exact = response.json()["exact"]
    assert exact["groups"] == 1
    assert exact["old_files"] == 1
    assert exact["new_files"] == 1
