from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from app.core.composer_pieces import (
    copy_composer_pieces_to_workspace,
    list_composer_piece_files,
    resolve_piece_folder_path,
)


def test_piece_folder_accepts_only_top_level_geom_and_xml(tmp_path):
    source = tmp_path / "parts"
    source.mkdir()
    (source / "part.smgXml").write_text("xml", encoding="utf-8")
    (source / "part.smgGeom").write_text("geometry", encoding="utf-8")

    assert {path.name for path in list_composer_piece_files(source)} == {
        "part.smgXml",
        "part.smgGeom",
    }


def test_copy_uses_nested_workspace_and_preserves_source(tmp_path):
    source = tmp_path / "parts"
    source.mkdir()
    original_xml = "<Document />"
    original_geom = "geometry"
    (source / "part.smgXml").write_text(original_xml, encoding="utf-8")
    (source / "part.smgGeom").write_text(original_geom, encoding="utf-8")

    workspace = copy_composer_pieces_to_workspace(source)

    assert workspace == source / "parts_optimized"
    assert {path.name for path in workspace.iterdir()} == {
        "part.smgXml",
        "part.smgGeom",
    }
    assert (source / "part.smgXml").read_text(encoding="utf-8") == original_xml
    assert (source / "part.smgGeom").read_text(encoding="utf-8") == original_geom


def test_copy_uses_unique_workspace_name_without_overwriting_existing_folder(tmp_path):
    source = tmp_path / "parts"
    source.mkdir()
    (source / "part.smgXml").write_text("<Document />", encoding="utf-8")
    existing = source / "parts_optimized"
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("existing", encoding="utf-8")

    workspace = copy_composer_pieces_to_workspace(source)

    assert workspace == source / "parts_optimized_2"
    assert marker.read_text(encoding="utf-8") == "existing"


def test_copy_stays_inside_input_root_when_source_is_root(tmp_path):
    source = tmp_path / "Input"
    source.mkdir()
    (source / "part.smgXml").write_text("<Document />", encoding="utf-8")

    workspace = copy_composer_pieces_to_workspace(source)

    assert workspace.parent == source
    assert workspace == source / "Input_optimized"


def test_local_piece_path_requires_local_bind_without_an_input_root(tmp_path):
    path = tmp_path / "parts"

    assert resolve_piece_folder_path(
        "",
        str(path),
        "127.0.0.1",
        invalid_path_code="PIECES_ROOT_PATH_INVALID",
        invalid_path_message="Absolute path required.",
    ) == path


def test_api_optimizes_a_copy_containing_only_piece_files(client, tmp_path):
    input_root = tmp_path / "input"
    source = input_root / "parts"
    source.mkdir(parents=True)
    xml_content = (
        '<Document><Server Type="CLitServerModifiable">'
        "<CLitTargetObject /><Neutral /></Server></Document>"
    )
    xml_path = source / "part.smgXml"
    geom_path = source / "part.smgGeom"
    xml_path.write_text(xml_content, encoding="utf-8")
    geom_path.write_text("geometry", encoding="utf-8")
    (source / "notes.txt").write_text("unrelated", encoding="utf-8")
    nested = source / "nested"
    nested.mkdir()
    (nested / "nested.smgXml").write_text("<Document />", encoding="utf-8")
    assert client.post(
        "/api/v1/settings",
        json={"onedrive_input_root": str(input_root)},
    ).status_code == 200

    count = client.post(
        "/api/v1/tree-optimization/count",
        json={"path": str(source)},
    )
    assert count.status_code == 200, count.text
    assert count.json()["files_count"] == 1

    response = client.post(
        "/api/v1/tree-optimization/run",
        json={"path": str(source), "apply": True},
    )

    assert response.status_code == 200, response.text
    workspace = source / "parts_optimized"
    assert response.json()["path"] == str(workspace)
    assert response.json()["files_modified"] == 1
    assert xml_path.read_text(encoding="utf-8") == xml_content
    assert geom_path.read_text(encoding="utf-8") == "geometry"
    assert {path.name for path in workspace.iterdir()} == {
        "part.smgXml",
        "part.smgGeom",
    }
    assert (workspace / "part.smgGeom").read_text(encoding="utf-8") == "geometry"
    assert ET.parse(workspace / "part.smgXml").find(".//CLitTargetObject") is None
    assert not list(workspace.glob("*.bak*"))


@pytest.mark.parametrize("invalid_entry", ["file", "subfolder"])
def test_api_counts_piece_files_when_source_has_other_entries(client, tmp_path, invalid_entry):
    input_root = tmp_path / "input"
    source = input_root / "parts"
    source.mkdir(parents=True)
    (source / "part.smgXml").write_text("<Document />", encoding="utf-8")
    if invalid_entry == "file":
        (source / "notes.txt").write_text("not a piece", encoding="utf-8")
    else:
        (source / "nested").mkdir()
    assert client.post(
        "/api/v1/settings",
        json={"onedrive_input_root": str(input_root)},
    ).status_code == 200

    response = client.post(
        "/api/v1/tree-optimization/count",
        json={"path": str(source)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["files_count"] == 1
