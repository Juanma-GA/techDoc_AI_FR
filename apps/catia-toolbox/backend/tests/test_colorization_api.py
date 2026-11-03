from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from openpyxl import Workbook


PROFILE_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<CLitStyleProperties>
  <Actor.Color R="192" G="192" B="192" />
  <Actor.Emission Value="0" />
  <Actor.Env.Effect Value="3" />
  <Actor.Env.Map.Path Value="C:\\3DVIAComposer_UserSets\\0_SN_Texture\\MetalBrushed.jpg" />
  <Actor.Outline.Width Value="0.995" />
  <Actor.Shininess Value="20" />
  <Texture.Map.Path Value="" />
  <Texture.UV.Ratio Value="51.1" />
  <Texture.UV.Scale Value="40.8" />
</CLitStyleProperties>
'''


def _make_piece(path, geometry_count: int = 1) -> bytes:
    root = ET.Element("DocumentSMG")
    for index in range(geometry_count):
        actor = ET.SubElement(root, "Neutral")
        ET.SubElement(actor, "Actor.Name", Value=f"Body {index + 1}")
        ET.SubElement(actor, "Actor.GeometryType", Value="1")
        ET.SubElement(actor, "Actor.Color", R="204", G="204", B="230", Defined="0")
        ET.SubElement(actor, "Actor.Prop.Area", Value=str(index + 10))
        ET.SubElement(actor, "Actor.ToolTip", Value=f"Body {index + 1}")
        location = ET.SubElement(actor, "Actor.Location")
        pivot = ET.SubElement(location, "Pivot")
        ET.SubElement(pivot, "Origin", X=str(index), Y="2", Z="3")
    non_geometry = ET.SubElement(root, "Neutral")
    ET.SubElement(non_geometry, "Actor.Name", Value="Annotation")
    ET.SubElement(non_geometry, "Actor.GeometryType", Value="0")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path.read_bytes()


def _make_run(client, root):
    workbook = Workbook()
    nomenclature = workbook.active
    nomenclature.title = "Nomenclature"
    nomenclature.append(["CATPart", "SIN", "OLD P/N"])
    nomenclature.append(["P1.CATPart", "SIN-1", "PN-001"])
    nomenclature.append(["P2.CATPart", "SIN-2", "PN-001"])
    nomenclature.append(["P3.CATPart", "SIN-3", "PN-002"])
    materials = workbook.create_sheet("Materiaux")
    materials.append(["SIN", "Slot 1", "Slot 2"])
    materials.append(["SIN-1", "STYLE-A", ""])
    materials.append(["SIN-2", "STYLE-A", "STYLE-A"])
    materials.append(["SIN-3", "STYLE-A", "STYLE-B"])
    path = root / "nomenclature.xlsx"
    workbook.save(path)
    run_response = client.post(
        "/api/v1/identification/nomenclature",
        json={"scope": "input", "path": str(path), "sheet": "Nomenclature"},
    )
    assert run_response.status_code == 200, run_response.text
    run_id = run_response.json()["id"]
    mono_response = client.post(
        "/api/v1/identification/mono-corps",
        json={
            "scope": "input",
            "path": str(path),
            "sheet": "Materiaux",
            "header_row": 1,
            "identity_field": "sin",
            "identity_col": 0,
            "first_slot_col": 1,
            "run_id": run_id,
        },
    )
    assert mono_response.status_code == 200, mono_response.text
    return run_id


def test_colorization_dry_run_and_apply_all_files_for_duplicate_old_pn(client, tmp_path):
    assert client.post(
        "/api/v1/settings", json={"onedrive_input_root": str(tmp_path)}
    ).status_code == 200
    pieces_root = tmp_path / "COMP PART"
    profiles_root = tmp_path / "Profiles"
    pieces_root.mkdir()
    profiles_root.mkdir()
    profile_path = profiles_root / "STYLE-A.smgStyleSet"
    profile_path.write_text(PROFILE_XML, encoding="utf-8")
    first_piece = pieces_root / "GE_001_PN-001_A_CATPart.smgXml"
    second_piece = pieces_root / "GE_002_PN_001_B_CATPart.smgXml"
    unrelated_piece = pieces_root / "GE_003_PN-002_CATPart.smgXml"
    prefix_collision_piece = pieces_root / "GE_004_PN-0010_CATPart.smgXml"
    original = {
        first_piece: _make_piece(first_piece, geometry_count=2),
        second_piece: _make_piece(second_piece, geometry_count=1),
        unrelated_piece: _make_piece(unrelated_piece, geometry_count=1),
        prefix_collision_piece: _make_piece(prefix_collision_piece, geometry_count=1),
    }
    run_id = _make_run(client, tmp_path)
    payload = {
        "scope": "input",
        "pieces_root": str(pieces_root),
        "profiles_root": str(profiles_root),
        "nomenclature_run_id": run_id,
    }

    dry = client.post("/api/v1/colorization/mono-body", json=payload)
    assert dry.status_code == 200, dry.text
    body = dry.json()
    assert body["summary"]["mono_parts"] == 2
    assert body["summary"]["files_found"] == 2
    assert body["summary"]["files_changed"] == 2
    assert body["summary"]["actors_changed"] == 3
    assert all(item["status"] == "planned" for item in body["items"])
    assert all(path.read_bytes() == content for path, content in original.items())

    applied = client.post("/api/v1/colorization/mono-body", json={**payload, "apply": True})
    assert applied.status_code == 200, applied.text
    assert applied.json()["summary"]["applied"] is True
    assert all("backup_path" not in item for item in applied.json()["items"])
    for path in (first_piece, second_piece):
        assert not path.with_name(path.name + ".bak").exists()
        root = ET.parse(path).getroot()
        actors = [
            actor
            for actor in root.findall("Neutral")
            if actor.find("Actor.GeometryType").get("Value") == "1"
        ]
        assert all(actor.find("Actor.Style").get("Value") == "STYLE-A.smgStyleSet" for actor in actors)
        assert all(actor.find("Actor.Env.Effect").get("Value") == "3" for actor in actors)
        assert all(actor.find("Actor.Prop.Area") is not None for actor in actors)
    assert unrelated_piece.read_bytes() == original[unrelated_piece]
    assert prefix_collision_piece.read_bytes() == original[prefix_collision_piece]


def test_colorization_rejects_paths_outside_scope(client, tmp_path):
    assert client.post(
        "/api/v1/settings", json={"onedrive_input_root": str(tmp_path)}
    ).status_code == 200
    outside = tmp_path.parent / "outside-profiles"
    outside.mkdir()
    run_id = _make_run(client, tmp_path)
    response = client.post(
        "/api/v1/colorization/mono-body",
        json={
            "scope": "input",
            "pieces_root": str(tmp_path),
            "profiles_root": str(outside),
            "nomenclature_run_id": run_id,
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "PATH_OUTSIDE_ROOT"


def test_colorization_uses_local_absolute_profiles_without_input_root(client, tmp_path):
    assert client.post(
        "/api/v1/settings", json={"onedrive_input_root": str(tmp_path)}
    ).status_code == 200
    run_id = _make_run(client, tmp_path)
    assert client.post("/api/v1/settings", json={"onedrive_input_root": ""}).status_code == 200

    pieces_root = tmp_path / "COMP PART"
    profiles_root = tmp_path / "Profiles"
    pieces_root.mkdir()
    profiles_root.mkdir()
    (profiles_root / "STYLE-A.smgStyleSet").write_text(PROFILE_XML, encoding="utf-8")
    piece_path = pieces_root / "GE_001_PN-001_CATPart.smgXml"
    _make_piece(piece_path)

    response = client.post(
        "/api/v1/colorization/mono-body",
        json={
            "scope": "input",
            "pieces_root": str(pieces_root),
            "profiles_root": str(profiles_root),
            "nomenclature_run_id": run_id,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["summary"]["files_found"] == 1
    assert response.json()["summary"]["files_changed"] == 1


@pytest.mark.parametrize("invalid_entry", ["file", "subfolder"])
def test_colorization_rejects_non_piece_entries(client, tmp_path, invalid_entry):
    assert client.post(
        "/api/v1/settings", json={"onedrive_input_root": str(tmp_path)}
    ).status_code == 200
    pieces_root = tmp_path / "COMP PART"
    profiles_root = tmp_path / "Profiles"
    pieces_root.mkdir()
    profiles_root.mkdir()
    if invalid_entry == "file":
        (pieces_root / "unexpected.txt").write_text("not a Composer piece", encoding="utf-8")
    else:
        (pieces_root / "nested").mkdir()
    run_id = _make_run(client, tmp_path)

    response = client.post(
        "/api/v1/colorization/mono-body",
        json={
            "scope": "input",
            "pieces_root": str(pieces_root),
            "profiles_root": str(profiles_root),
            "nomenclature_run_id": run_id,
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PIECES_FOLDER_CONTENT_INVALID"