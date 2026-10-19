from __future__ import annotations

import xml.etree.ElementTree as ET

from app.core.smgxml_colorization import colorize_mono_body_folder


PROFILE_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<CLitStyleProperties>
  <Actor.Color R="192" G="192" B="192" />
  <Actor.Emission Value="0" />
  <Actor.Env.Effect Value="3" />
  <Actor.Env.Map.Path Value="C:\\3DVIAComposer_UserSets\\0_SN_Texture\\MetalBrushed.jpg" />
  <Actor.Outline.Width Value="0.995" />
  <Actor.Prop.Area Value="999" />
  <Actor.Shininess Value="20" />
  <Actor.ToolTip Value="PROFILE_TOOLTIP" />
  <Texture.Map.Path Value="" />
  <Texture.UV.Ratio Value="51.1" />
  <Profile.AssociatedFile Value="C:\\profiles\\STYLE-A.smgStyleSet" />
</CLitStyleProperties>
'''


def _make_piece(path, geometry_count: int, include_non_geometry: bool = True) -> bytes:
    root = ET.Element("DocumentSMG")
    for index in range(geometry_count):
        neutral = ET.SubElement(root, "Neutral")
        ET.SubElement(neutral, "Actor.Name", Value=f"Body {index + 1}")
        ET.SubElement(neutral, "Actor.GeometryType", Value="1")
        ET.SubElement(neutral, "Actor.Prop.Area", Value=str(index + 10))
        ET.SubElement(neutral, "Actor.ToolTip", Value=f"Body {index + 1}")
        location = ET.SubElement(neutral, "Actor.Location")
        pivot = ET.SubElement(location, "Pivot")
        ET.SubElement(pivot, "Origin", X=str(index), Y="2", Z="3")
    if include_non_geometry:
        neutral = ET.SubElement(root, "Neutral")
        ET.SubElement(neutral, "Actor.Name", Value="Annotation")
        ET.SubElement(neutral, "Actor.GeometryType", Value="0")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path.read_bytes()


def _create_fixture(tmp_path):
    pieces_root = tmp_path / "pieces"
    profiles_root = tmp_path / "profiles"
    pieces_root.mkdir()
    profiles_root.mkdir()
    profile_path = profiles_root / "STYLE-A.smgStyleSet"
    profile_path.write_text(PROFILE_XML, encoding="utf-8")
    first_piece = pieces_root / "GE_001_PN-001_A_CATPart.smgXml"
    second_piece = pieces_root / "GE_002_PN_001_B_CATPart.smgXml"
    unrelated_piece = pieces_root / "GE_003_PN-002_CATPart.smgXml"
    first_original = _make_piece(first_piece, geometry_count=2)
    second_original = _make_piece(second_piece, geometry_count=1)
    unrelated_original = _make_piece(unrelated_piece, geometry_count=1)
    mono_parts = [
        {"old_pn": "PN-001", "mono_texture": "STYLE-A"},
        {"old_pn": "PN-001", "mono_texture": "STYLE-A"},
    ]
    return pieces_root, profiles_root, mono_parts, {
        first_piece: first_original,
        second_piece: second_original,
        unrelated_piece: unrelated_original,
    }


def test_colorization_dry_run_includes_all_files_and_repeated_actors(tmp_path):
    pieces_root, profiles_root, mono_parts, original_bytes = _create_fixture(tmp_path)

    result = colorize_mono_body_folder(pieces_root, profiles_root, mono_parts, apply=False)

    assert result["summary"]["files_found"] == 2
    assert result["summary"]["files_changed"] == 2
    assert result["summary"]["actors_changed"] == 3
    assert {item["status"] for item in result["items"]} == {"planned"}
    for path, content in original_bytes.items():
        assert path.read_bytes() == content
        assert not path.with_name(path.name + ".bak").exists()


def test_colorization_apply_preserves_non_style_properties_without_backup(tmp_path):
    pieces_root, profiles_root, mono_parts, original_bytes = _create_fixture(tmp_path)

    result = colorize_mono_body_folder(pieces_root, profiles_root, mono_parts, apply=True)

    assert result["summary"]["files_changed"] == 2
    assert result["summary"]["actors_changed"] == 3
    assert result["summary"]["applied"] is True
    assert all("backup_path" not in item for item in result["items"])
    for path, original in original_bytes.items():
        if "PN-002" in path.name:
            assert path.read_bytes() == original
            continue
        assert not path.with_name(path.name + ".bak").exists()
        root = ET.parse(path).getroot()
        geometry_actors = [
            neutral
            for neutral in root.findall("Neutral")
            if neutral.find("Actor.GeometryType").get("Value") == "1"
        ]
        for actor in geometry_actors:
            assert actor.find("Actor.Style").get("Value") == "STYLE-A.smgStyleSet"
            assert actor.find("Actor.Env.Map.Path").get("Value") == (
                r"C:\3DVIAComposer_UserSets\0_SN_Texture\MetalBrushed.jpg"
            )
            assert actor.find("Actor.Prop.Area").get("Value") in {"10", "11"}
            assert actor.find("Actor.ToolTip").get("Value").startswith("Body ")
            assert actor.find("Profile.AssociatedFile") is None
        non_geometry = next(
            neutral
            for neutral in root.findall("Neutral")
            if neutral.find("Actor.GeometryType").get("Value") == "0"
        )
        assert non_geometry.find("Actor.Style") is None


def test_colorization_skips_conflicting_profiles_for_same_old_pn(tmp_path):
    pieces_root, profiles_root, _mono_parts, original_bytes = _create_fixture(tmp_path)
    (profiles_root / "STYLE-B.smgStyleSet").write_text(PROFILE_XML, encoding="utf-8")
    conflicting_parts = [
        {"old_pn": "PN-001", "mono_texture": "STYLE-A"},
        {"old_pn": "PN-001", "mono_texture": "STYLE-B"},
    ]

    result = colorize_mono_body_folder(pieces_root, profiles_root, conflicting_parts, apply=True)

    assert result["summary"]["applied"] is False
    assert {item["status"] for item in result["items"]} == {"style_conflict"}
    for path, content in original_bytes.items():
        assert path.read_bytes() == content