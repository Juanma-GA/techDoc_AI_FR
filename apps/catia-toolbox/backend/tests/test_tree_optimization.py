"""Tests for the Composer tree optimization operation."""

from __future__ import annotations

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


def test_count_smgxml_files_only_checks_top_level_names(tmp_path):
    source = tmp_path / "composer"
    nested = source / "nested"
    backups = source / "sauvegarde"
    nested.mkdir(parents=True)
    backups.mkdir()
    (source / "piece.smgXml").write_text("not parsed", encoding="utf-8")
    (source / "another.SMGXML").write_text("also not parsed", encoding="utf-8")
    (source / "other.xml").write_text("not counted", encoding="utf-8")
    (nested / "nested.smgXml").write_text("not counted", encoding="utf-8")
    (backups / "piece.smgXml.bak").write_text("not counted", encoding="utf-8")

    assert count_smgxml_files(source) == 2


def test_analyze_only_top_level_smgxml_without_writing(tmp_path):
    source = tmp_path / "composer"
    nested = source / "nested"
    nested.mkdir(parents=True)
    xml_path = source / "piece.smgXml"
    original = _composer_xml()
    xml_path.write_text(original, encoding="utf-8")
    (source / "not-a-piece.xml").write_text(original, encoding="utf-8")
    (nested / "nested.smgXml").write_text(original, encoding="utf-8")

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


def test_apply_keeps_allowed_trees_and_outside_content_with_backup(tmp_path):
    source = tmp_path / "composer"
    source.mkdir()
    xml_path = source / "piece.smgXml"
    xml_path.write_text(_composer_xml(), encoding="utf-8")

    result = optimize_folder(source, apply=True)

    item = result["files"][0]
    assert item["status"] == "optimized"
    assert item["backup_path"] == str(source / "sauvegarde" / "piece.smgXml.bak")
    assert result["files_modified"] == 1
    backup_path = item["backup_path"]
    assert backup_path is not None
    original_root = ET.parse(backup_path).getroot()
    root = ET.parse(xml_path).getroot()
    assert original_root.find(".//CLitTargetObject") is not None
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


def test_api_analyzes_then_applies_with_backup(client, tmp_path):
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
    assert (folder / "sauvegarde" / "piece.smgXml.bak").read_text(encoding="utf-8") == original
    assert ET.parse(xml_path).find(".//CLitTargetObject") is None


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


def test_api_count_uses_names_only_without_parsing_or_recursion(client, tmp_path):
    root = tmp_path / "input"
    folder = root / "composer"
    nested = folder / "nested"
    nested.mkdir(parents=True)
    assert client.post(
        "/api/v1/settings",
        json={"onedrive_input_root": str(root)},
    ).status_code == 200
    (folder / "broken.smgXml").write_text("<invalid", encoding="utf-8")
    (folder / "other.xml").write_text("<root />", encoding="utf-8")
    (nested / "nested.smgXml").write_text("<root />", encoding="utf-8")

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


def test_existing_backup_is_not_overwritten(tmp_path):
    source = tmp_path / "composer"
    backup_directory = source / "sauvegarde"
    backup_directory.mkdir(parents=True)
    xml_path = source / "piece.smgXml"
    xml_path.write_text(_composer_xml(), encoding="utf-8")
    existing_backup = backup_directory / "piece.smgXml.bak"
    existing_backup.write_text("previous backup", encoding="utf-8")

    result = optimize_folder(source, apply=True)

    assert result["files"][0]["backup_path"] == str(backup_directory / "piece.smgXml.bak.1")
    assert existing_backup.read_text(encoding="utf-8") == "previous backup"
