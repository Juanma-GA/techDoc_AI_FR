from __future__ import annotations

import json

from openpyxl import Workbook

from app.core import dmrl
from app.core.dmrl_rules import is_pm_title
from app.core.errors import AppError
from app.core.info_code_types import load_info_code_schemas


def _write_reference(path, rows: list[tuple[object, object]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Info code", "Schéma recommandé"])
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()


def test_load_info_code_schemas_normalizes_codes_and_schema_names(tmp_path) -> None:
    path = tmp_path / "info-codes.xlsx"
    _write_reference(
        path,
        [(0, "descript"), (520, "proced"), (941, "ipd"), (1, "frontmatter")],
    )

    assert load_info_code_schemas(path) == {
        "000": "descript",
        "520": "proced",
        "941": "ipd",
        "001": "frontmatter",
    }


def test_load_info_code_schemas_rejects_conflicting_duplicate_codes(tmp_path) -> None:
    path = tmp_path / "info-codes.xlsx"
    _write_reference(path, [("520", "proced"), ("520", "descript")])

    try:
        load_info_code_schemas(path)
    except AppError as exc:
        assert exc.code == "INFO_CODE_MAP_INVALID"
    else:
        raise AssertionError("Conflicting InfoCode mappings must not be accepted.")


def test_issue_41_type_uses_infocode_and_preserves_dmrl_conflicts(tmp_path, monkeypatch) -> None:
    path = tmp_path / "dmrl.json"
    path.write_text(
        json.dumps([
            {
                "DMC": "DMC-PUMP-A-00-00-00-00A-520A-D",
                "Infocode": "520",
                "Titre": "Removal Procedure",
                "Type": "Descriptif",
            },
            {
                "DMC": "DMC-PUMP-A-00-00-00-00A-040A-D",
                "Infocode": "040",
                "Titre": "Description",
                "Type": "Descriptif",
            },
            {
                "DMC": "DMC-PUMP-A-00-00-00-00A-001A-D",
                "Infocode": "001",
                "Titre": "Front matter",
                "Type": "Descriptif",
            },
            {
                "DMC": "DMC-PUMP-A-00-00-00-00A-999A-D",
                "Infocode": "999",
                "Titre": "Unmapped",
                "Type": "Descriptif",
            },
            {
                "MIC": "PUMP",
                "Titre": "Missing InfoCode",
                "Type": "Descriptif",
            },
            {"MIC": "PUMP2", "Titre": "No type or InfoCode"},
            {
                "DMC": "DMC-PUMP-A-00-00-00-00A-998A-D",
                "Infocode": "998",
                "Titre": "Unmapped without a DMRL type",
            },
            {"Titre": "Publication title only"},
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        dmrl,
        "load_info_code_schemas",
        lambda: {
            "520": "proced",
            "040": "descript",
            "001": "frontmatter",
        },
    )

    entries = dmrl.load_dmrl(path, issue="4.1")

    conflict, matching, unsupported, unmapped, missing, defaulted, unmapped_defaulted, pm_title = entries
    assert conflict.dm_type == ""
    assert conflict.type_conflict is True
    assert conflict.dmrl_type == "Descriptif"
    assert conflict.info_code_dm_type == "procedural"
    assert dmrl.entry_from_dict(conflict.to_dict()).type_conflict is True
    assert matching.dm_type == "descriptive"
    assert matching.type_conflict is False
    assert unsupported.type_issue == "unsupported_schema"
    assert unsupported.info_code_schema == "frontmatter"
    assert unsupported.type_conflict is True
    assert unsupported.dm_type == ""
    assert unmapped.type_issue == "unmapped_info_code"
    assert missing.type_issue == "missing_info_code"
    assert missing.dm_type == ""
    assert defaulted.type_issue == "missing_info_code"
    assert defaulted.dm_type == "descriptive"
    assert unmapped_defaulted.type_issue == "unmapped_info_code"
    assert unmapped_defaulted.dm_type == "descriptive"
    assert is_pm_title(pm_title)
    assert pm_title.dm_type == ""


def test_non_41_dmrl_keeps_legacy_type_precedence(tmp_path, monkeypatch) -> None:
    path = tmp_path / "dmrl.json"
    path.write_text(
        json.dumps([{
            "DMC": "DMC-PUMP-A-00-00-00-00A-520A-D",
            "Infocode": "520",
            "Titre": "Removal Procedure",
            "Type": "Descriptif",
        }]),
        encoding="utf-8",
    )

    def unexpected_mapping_load():
        raise AssertionError("The Issue 4.1 workbook must not be read for other issues.")

    monkeypatch.setattr(dmrl, "load_info_code_schemas", unexpected_mapping_load)

    assert dmrl.load_dmrl(path, issue="4.2")[0].dm_type == "descriptive"


def test_issue_41_conflict_must_be_resolved_before_generation(client, pdf_bytes, monkeypatch) -> None:
    monkeypatch.setattr(dmrl, "load_info_code_schemas", lambda: {"520": "proced"})

    document_response = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", pdf_bytes, "application/pdf")},
        data={"s1000d_issue": "4.1", "context_hint": "mixed"},
    )
    assert document_response.status_code == 201, document_response.text
    doc_id = document_response.json()["id"]

    detection_response = client.post(f"/api/v1/documents/{doc_id}/pdf-cut/detect")
    assert detection_response.status_code == 200, detection_response.text
    detection = detection_response.json()
    if detection["validation_required"]:
        confirmation = client.post(
            f"/api/v1/documents/{doc_id}/pdf-cut/confirm",
            json={
                "start_page": detection["selected_page"] or detection["default_start_page"],
                "end_page": detection["selected_end_page"] or detection["total_pages"],
            },
        )
        assert confirmation.status_code == 200, confirmation.text

    dmrl_rows = [{
        "DMC": "DMC-PUMP-A-00-00-00-00A-520A-D",
        "Infocode": "520",
        "Titre": "Description",
        "Type": "Descriptif",
    }]
    upload_response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("DMRL.json", json.dumps(dmrl_rows).encode())},
    )
    assert upload_response.status_code == 200, upload_response.text

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert state["step"] == "dmrl"
    assert state["dmrl"][0]["type_conflict"] is True
    assert state["dmrl"][0]["dm_type"] == ""

    blocked = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "DMRL_TYPE_REVIEW_REQUIRED"

    updated = client.post(
        f"/api/v1/documents/{doc_id}/wizard/update",
        json={"op": "set_type", "index": 0, "dm_type": "procedural"},
    ).json()
    assert updated["dmrl"][0]["dm_type"] == "procedural"

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "split"
    assert state["dms"][0]["dm_type"] == "procedural"
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "type"
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance",
        json={"types": {}},
    ).json()
    assert state["step"] == "structure"
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/advance",
        json={"overrides": []},
    ).json()
    assert state["step"] == "generate"
    assert state["dms"][0]["dm_type"] == "procedural"

    generated_xml = client.get(
        f"/api/v1/documents/{doc_id}/wizard/dm/{state['dms'][0]['dm_id']}/xml"
    ).text
    assert "<procedure>" in generated_xml
