"""Tests for the Composer tree optimization operation."""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from types import ModuleType

import pytest

from app.api import tree_optimization as tree_optimization_api
from app.core.tree_optimization import count_smgxml_files, optimize_folder


def _composer_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<Document>
  <!-- outside comment -->
  <Outside Keep="yes"><CLitActorGround /></Outside>
  <Server Type="CLitServerBase"><CLitVectorImageBOM /></Server>
  <Server Type="CLitServerModifiable">
    <CLitAssyRoot Ident="-1" NodeType="0">
      <Neutral><Actor.Name Value="ROOT" /></Neutral>
      <CLitTargetObject><Neutral><Anchor /></Neutral></CLitTargetObject>
      <Tracks />
            <CLitActorMesh Ident="mesh-1">
                <MeshAttributes />
                <Neutral><Actor.Name Value="PART" /></Neutral>
            </CLitActorMesh>
      <CLitVectorImageBOM />
      <CLitAssyRoot><Neutral /><CLitActorMesh Ident="mesh-2" /></CLitAssyRoot>
    </CLitAssyRoot>
    <Neutral><Actor.Name Value="SERVER" /></Neutral>
    <Tracks />
    <CLitActorMesh Ident="mesh-3" />
    <CLitActorGround />
  </Server>
</Document>
"""


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def test_count_smgxml_files_ignores_unrelated_source_entries(tmp_path):
    source = tmp_path / "composer"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (source / "piece.smgXml").write_text("not parsed", encoding="utf-8")
    (source / "another.SMGXML").write_text("also not parsed", encoding="utf-8")
    (source / "piece.smgGeom").write_text("geometry", encoding="utf-8")
    (source / "notes.txt").write_text("unrelated", encoding="utf-8")
    (nested / "nested.smgXml").write_text("ignored", encoding="utf-8")

    assert count_smgxml_files(source) == 2


def test_analyze_only_top_level_smgxml_without_writing(tmp_path):
    source = tmp_path / "composer"
    source.mkdir()
    xml_path = source / "piece.smgXml"
    original = _composer_xml()
    xml_path.write_text(original, encoding="utf-8")
    (source / "piece.smgGeom").write_text("geometry", encoding="utf-8")

    result = optimize_folder(source)

    assert result["files_scanned"] == 1
    assert result["files_with_changes"] == 1
    assert result["files_modified"] == 0
    assert result["files"][0]["status"] == "ready"
    assert result["files"][0]["removed_by_tag"] == {
        "CLitTargetObject": 1,
        "CLitVectorImageBOM": 1,
        "CLitActorGround": 1,
    }
    assert xml_path.read_text(encoding="utf-8") == original
    assert not (source / "sauvegarde").exists()


def test_apply_keeps_allowed_trees_and_outside_content_without_backup(tmp_path):
    source = tmp_path / "composer"
    source.mkdir()
    xml_path = source / "piece.smgXml"
    xml_path.write_text(_composer_xml(), encoding="utf-8")

    result = optimize_folder(source, apply=True)

    item = result["files"][0]
    assert item["status"] == "optimized"
    assert "backup_path" not in item
    assert result["files_modified"] == 1
    assert not (source / "sauvegarde").exists()
    root = ET.parse(xml_path).getroot()
    assert root.find(".//CLitTargetObject") is None
    assert root.find(".//Outside/CLitActorGround") is not None
    assert root.find(".//Server[@Type='CLitServerBase']/CLitVectorImageBOM") is not None
    assert root.find(".//CLitActorMesh[@Ident='mesh-1']/MeshAttributes") is not None
    assert root.find(".//CLitActorMesh[@Ident='mesh-1']/Neutral/Actor.Name") is not None
    assert len(root.findall(".//CLitActorMesh")) == 3
    assert all(
        _tag(child) in {"CLitAssyRoot", "Neutral", "Tracks", "CLitActorMesh"}
        for server in root.findall(".//Server[@Type='CLitServerModifiable']")
        for child in list(server)
    )
    assert all(
        _tag(child) in {"CLitAssyRoot", "Neutral", "Tracks", "CLitActorMesh"}
        for assy_root in root.findall(".//CLitAssyRoot")
        for child in list(assy_root)
    )
    assert "outside comment" in xml_path.read_text(encoding="utf-8")


def test_assy_groups_are_removed_and_actor_meshes_are_hoisted(tmp_path):
        source = tmp_path / "composer"
        source.mkdir()
        xml_path = source / "grouped-piece.smgXml"
        xml_path.write_text(
                """<Document><Server Type="CLitServerModifiable">
    <CLitAssyRoot>
        <CLitAssyGroup Ident="group-with-mesh">
            <Neutral><Actor.Name Value="Group" /></Neutral>
            <CLitTargetObject />
            <CLitActorMesh Ident="mesh-direct" />
            <CLitAssyGroup Ident="nested-group"><CLitActorMesh Ident="mesh-nested" /></CLitAssyGroup>
        </CLitAssyGroup>
        <CLitAssyGroup Ident="empty-group"><Neutral /></CLitAssyGroup>
    </CLitAssyRoot>
</Server></Document>""",
                encoding="utf-8",
        )

        result = optimize_folder(source, apply=True)
        root = ET.parse(xml_path).getroot()

        assert result["files_modified"] == 1
        assert root.find(".//CLitAssyGroup") is None
        assy_root = root.find(".//CLitAssyRoot")
        assert assy_root is not None
        assert assy_root.find("./CLitActorMesh[@Ident='mesh-direct']") is not None
        assert assy_root.find("./CLitActorMesh[@Ident='mesh-nested']") is not None
        assert assy_root.find("./Neutral/Actor.Name[@Value='Group']") is None
        assert root.find(".//CLitTargetObject") is None


def test_unmatched_and_invalid_xml_are_reported_without_backups(tmp_path):
    source = tmp_path / "composer"
    source.mkdir()
    no_section = source / "no-section.smgXml"
    invalid = source / "invalid.smgXml"
    no_section.write_text("<Document><Outside /></Document>", encoding="utf-8")
    invalid.write_text("<Document>", encoding="utf-8")

    result = optimize_folder(source, apply=True)

    statuses = {item["path"]: item["status"] for item in result["files"]}
    assert statuses[str(no_section)] == "no_section"
    assert statuses[str(invalid)] == "invalid_xml"
    assert result["files_modified"] == 0
    assert not (source / "sauvegarde").exists()


def test_api_analyzes_then_applies_to_copy_without_backup(client, tmp_path):
    assert (
        client.post(
            "/api/v1/settings",
            json={"onedrive_input_root": str(tmp_path)},
        ).status_code
        == 200
    )
    folder = tmp_path / "composer"
    folder.mkdir()
    xml_path = folder / "piece.smgXml"
    original = _composer_xml()
    xml_path.write_text(original, encoding="utf-8")

    count_response = client.post(
        "/api/v1/tree-optimization/count",
        json={"path": str(folder)},
    )
    assert count_response.status_code == 200, count_response.text
    assert count_response.json()["files_count"] == 1

    applied = client.post(
        "/api/v1/tree-optimization/run",
        json={"path": str(folder), "apply": True},
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["applied"] is True
    assert body["files_scanned"] == 1
    assert body["files_modified"] == 1
    assert body["removed_elements"] > 0
    assert "files" not in body
    output = folder / "composer_optimized"
    assert body["path"] == str(output)
    assert xml_path.read_text(encoding="utf-8") == original
    assert ET.parse(output / xml_path.name).find(".//CLitTargetObject") is None
    assert not (output / "sauvegarde").exists()


def test_api_streams_tree_optimization_progress(client, tmp_path):
    assert (
        client.post(
            "/api/v1/settings",
            json={"onedrive_input_root": str(tmp_path)},
        ).status_code
        == 200
    )
    folder = tmp_path / "composer"
    folder.mkdir()
    (folder / "first.smgXml").write_text("<Document />", encoding="utf-8")
    (folder / "second.smgXml").write_text("<Document />", encoding="utf-8")

    response = client.post(
        "/api/v1/tree-optimization/run-stream",
        json={"path": str(folder), "apply": False},
    )

    assert response.status_code == 200, response.text
    events = [json.loads(line) for line in response.text.splitlines()]
    progress = [event for event in events if event["type"] == "progress"]
    assert [(event["files_scanned"], event["files_total"]) for event in progress] == [
        (0, 2),
        (1, 2),
        (2, 2),
    ]
    assert events[-1]["type"] == "complete"
    assert events[-1]["result"]["files_scanned"] == 2


def test_api_rejects_folder_outside_input_root(client, tmp_path):
    input_root = tmp_path / "input"
    outside = tmp_path / "outside"
    input_root.mkdir()
    outside.mkdir()
    assert (
        client.post(
            "/api/v1/settings",
            json={"onedrive_input_root": str(input_root)},
        ).status_code
        == 200
    )

    response = client.post(
        "/api/v1/tree-optimization/run",
        json={"path": str(outside), "apply": True},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PATH_OUTSIDE_ROOT"


def test_api_folder_picker_returns_only_the_selected_path(client, tmp_path, monkeypatch):
    initial = tmp_path / "initial"
    selected = tmp_path / "composer"
    initial.mkdir()
    selected.mkdir()
    monkeypatch.setattr(tree_optimization_api, "_is_local_request", lambda _request: True)

    def choose_folder(initial_path, title):
        assert initial_path == str(initial)
        assert title == "Composer parts folder"
        return str(selected)

    monkeypatch.setattr(tree_optimization_api, "_open_folder_dialog", choose_folder)
    response = client.post(
        "/api/v1/tree-optimization/pick-folder",
        json={"initial_path": str(initial), "title": "Composer parts folder"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"path": str(selected.resolve())}


def test_api_folder_picker_cancel_returns_no_path(client, monkeypatch):
    monkeypatch.setattr(tree_optimization_api, "_is_local_request", lambda _request: True)
    monkeypatch.setattr(tree_optimization_api, "_open_folder_dialog", lambda _initial, _title: None)

    response = client.post("/api/v1/tree-optimization/pick-folder", json={})

    assert response.status_code == 200, response.text
    assert response.json() == {"path": None}


def test_api_folder_picker_rejects_non_local_requests(client, monkeypatch):
    monkeypatch.setattr(tree_optimization_api, "_is_local_request", lambda _request: False)
    monkeypatch.setattr(
        tree_optimization_api,
        "_open_folder_dialog",
        lambda _initial, _title: (_ for _ in ()).throw(AssertionError("dialog must not open")),
    )

    response = client.post("/api/v1/tree-optimization/pick-folder", json={})

    assert response.status_code == 403
    assert response.json()["code"] == "LOCAL_FOLDER_PICKER_ONLY"


@pytest.mark.skipif(os.name != "nt", reason="PySide6 folder dialog is Windows-only")
def test_qt_folder_dialog_uses_directory_picker_and_returns_path(client, tmp_path, monkeypatch):
    initial = tmp_path / "initial"
    selected = tmp_path / "selected"
    initial.mkdir()
    selected.mkdir()
    selected_paths = iter((str(selected), ""))
    calls = []

    class FakeApplication:
        current = None

        def __init__(self, _arguments):
            type(self).current = self

        @classmethod
        def instance(cls):
            return cls.current

        def set_quit_on_last_window_closed(self, value):
            calls.append(("quit", value))

    class FakeFileDialog:
        class Option:
            ShowDirsOnly = object()

        @staticmethod
        def get_existing_directory(parent, title, initial_dir, options):
            calls.append((parent, title, initial_dir, options))
            return next(selected_paths)

    application_method_name = "setQuitOnLastWindowClosed"
    folder_dialog_method_name = "getExistingDirectory"
    setattr(FakeApplication, application_method_name, FakeApplication.set_quit_on_last_window_closed)
    setattr(FakeFileDialog, folder_dialog_method_name, staticmethod(FakeFileDialog.get_existing_directory))

    qt_package = ModuleType("PySide6")
    qt_package.__path__ = []
    qt_widgets = ModuleType("PySide6.QtWidgets")
    qt_widgets.__dict__["QApplication"] = FakeApplication
    qt_widgets.__dict__["QFileDialog"] = FakeFileDialog
    monkeypatch.setitem(sys.modules, "PySide6", qt_package)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qt_widgets)
    monkeypatch.setattr(tree_optimization_api, "_is_local_request", lambda _request: True)
    monkeypatch.setattr(tree_optimization_api, "_QT_APPLICATION", None)

    response = client.post(
        "/api/v1/tree-optimization/pick-folder",
        json={"initial_path": str(initial), "title": "Composer folder"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"path": str(selected.resolve())}
    assert calls[0] == ("quit", False)
    assert calls[1] == (None, "Composer folder", str(initial), FakeFileDialog.Option.ShowDirsOnly)
    canceled = client.post(
        "/api/v1/tree-optimization/pick-folder",
        json={"title": "Composer folder"},
    )
    assert canceled.status_code == 200
    assert canceled.json() == {"path": None}


def test_api_accepts_absolute_local_path_without_upload(client, tmp_path):
    folder = tmp_path / "composer"
    folder.mkdir()
    xml_path = folder / "piece.smgXml"
    xml_path.write_text(_composer_xml(), encoding="utf-8")

    response = client.post(
        "/api/v1/tree-optimization/run",
        json={"path": str(folder)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["files_scanned"] == 1
    assert response.json()["files_with_changes"] == 1
    assert "files" not in response.json()
    assert xml_path.read_text(encoding="utf-8") == _composer_xml()
    output = folder / "composer_optimized"
    assert response.json()["path"] == str(output)
    assert (output / xml_path.name).read_text(encoding="utf-8") == _composer_xml()


def test_api_count_ignores_unrelated_source_entries_without_parsing(client, tmp_path):
    root = tmp_path / "input"
    folder = root / "composer"
    nested = folder / "nested"
    folder.mkdir(parents=True)
    nested.mkdir()
    assert client.post(
        "/api/v1/settings",
        json={"onedrive_input_root": str(root)},
    ).status_code == 200
    (folder / "broken.smgXml").write_text("<invalid", encoding="utf-8")
    (folder / "piece.smgGeom").write_text("geometry", encoding="utf-8")
    (folder / "notes.txt").write_text("unrelated", encoding="utf-8")
    (nested / "nested.smgXml").write_text("ignored", encoding="utf-8")

    response = client.post(
        "/api/v1/tree-optimization/count",
        json={"path": str(folder)},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"path": str(folder), "files_count": 1}


def test_api_requires_input_root_for_nonlocal_bind(client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "bind_host", "0.0.0.0")
    response = client.post(
        "/api/v1/tree-optimization/run",
        json={"path": str(tmp_path)},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ROOT_NOT_CONFIGURED"


def test_apply_does_not_create_a_backup(tmp_path):
    source = tmp_path / "composer"
    source.mkdir()
    xml_path = source / "piece.smgXml"
    xml_path.write_text(_composer_xml(), encoding="utf-8")

    result = optimize_folder(source, apply=True)

    assert result["files"][0]["status"] == "optimized"
    assert not (source / "sauvegarde").exists()
    assert not list(source.glob("*.bak*"))
