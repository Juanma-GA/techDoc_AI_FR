from __future__ import annotations

import json

from lxml import etree

from app.core.dmrl import DmrlEntry
from app.core.dmrl_rules import data_module_entries, is_pm_title

_DMC = "DMC-PUMP-A-00-00-00-00A-040A-D"
_ICN = "ICN-WEG-AA0004-00001-A-02.png"


def _upload_doc(client, data: bytes) -> str:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", data)},
        data={"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    assert response.status_code == 201, response.text
    doc_id = response.json()["id"]
    detection = client.post(f"/api/v1/documents/{doc_id}/pdf-cut/detect")
    assert detection.status_code == 200, detection.text
    cut = detection.json()
    if cut["validation_required"]:
        response = client.post(
            f"/api/v1/documents/{doc_id}/pdf-cut/confirm",
            json={
                "start_page": cut["selected_page"] or cut["default_start_page"],
                "end_page": cut["selected_end_page"] or cut["total_pages"],
            },
        )
        assert response.status_code == 200, response.text
    return doc_id


def _upload_dmrl(client, doc_id: str, entries: list[dict]) -> None:
    response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("DMRL.json", json.dumps(entries).encode())},
    )
    assert response.status_code == 200, response.text


def test_title_only_rows_are_kept_in_pmc_and_not_generated_as_dms(
    client, pdf_bytes_image
) -> None:
    doc_id = _upload_doc(client, pdf_bytes_image)
    _upload_dmrl(client, doc_id, [
        {"Arbo": "1", "Titre": "Vue générale"},
        {
            "Arbo": "1.1",
            "DMC": _DMC,
            "Titre": "Description",
            "Type": "Descriptif",
            "ICN": _ICN,
        },
    ])

    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/start",
        json={"start_page": 1},
    ).json()
    assert state["dmrl_dm_count"] == 1
    assert state["dmrl"][0]["is_pm_title"] is True
    assert state["dmrl"][0]["matched"] is False
    assert state["dmrl"][1]["is_pm_title"] is False
    assert state["dmrl"][1]["matched"] is True

    pmc_response = client.get(f"/api/v1/documents/{doc_id}/pmc")
    assert pmc_response.status_code == 200, pmc_response.text
    pm = etree.fromstring(pmc_response.content)
    title_entry = pm.find("./content/pmEntry")
    assert title_entry is not None
    assert title_entry.findtext("./pmEntryTitle") == "Vue générale"
    assert title_entry.find("./dmRef") is None
    dm_entry = title_entry.find("./pmEntry")
    assert dm_entry is not None
    assert dm_entry.findtext("./pmEntryTitle") == "Description"
    assert dm_entry.find("./dmRef/dmRefIdent/dmCode") is not None

    validation = client.post(
        f"/api/v1/documents/{doc_id}/validate-and-generate-pmc"
    )
    assert validation.status_code == 200
    assert "event: done" in validation.text
    assert "event: error" not in validation.text

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "split"
    assert state["resources"]["dmrl_count"] == 2
    assert state["dmrl_dm_count"] == 1
    assert [dm["title"] for dm in state["dms"]] == ["Description"]

    image_names = client.get(f"/api/v1/documents/{doc_id}/wizard/images").json()
    assert image_names == [_ICN]
    for payload in ({}, {"types": {}}, {"overrides": []}):
        state = client.post(
            f"/api/v1/documents/{doc_id}/wizard/advance",
            json=payload,
        ).json()

    dm_id = state["dms"][0]["dm_id"]
    download = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{dm_id}/xml")
    assert download.status_code == 200, download.text
    xml = download.text
    assert "\n  <identAndStatusSection>" in xml
    assert "\n    <dmAddress>" in xml
    assert (
        f'<!ENTITY ICN-WEG-AA0004-00001-A-02 SYSTEM "{_ICN}" NDATA png>' in xml
    )
    assert 'infoEntityIdent="ICN-WEG-AA0004-00001-A-02"' in xml


def test_missing_dm_is_reported_without_treating_pm_title_as_missing(
    client, pdf_bytes
) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    _upload_dmrl(client, doc_id, [
        {"Arbo": "1", "Titre": "Rubrique éditoriale"},
        {
            "Arbo": "1.1",
            "DMC": _DMC,
            "Titre": "Chapitre absent",
            "Type": "Descriptif",
        },
    ])

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()

    assert state["dmrl_dm_count"] == 1
    assert state["dmrl"][0]["is_pm_title"] is True
    assert state["dmrl"][1]["is_pm_title"] is False
    assert state["dmrl"][1]["matched"] is False


def test_dmrl_with_only_pm_titles_does_not_drive_the_dm_split(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    _upload_dmrl(client, doc_id, [
        {"Arbo": "1", "Titre": "Sommaire opérateur"},
    ])

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert state["dmrl_dm_count"] == 0

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "split"
    assert state["dms"]
    assert all(dm["title"] != "Sommaire opérateur" for dm in state["dms"])


def test_only_title_and_hierarchy_are_classified_as_pm_titles() -> None:
    pm_title = DmrlEntry(arbo="1", title="Introduction")
    partial_dm = DmrlEntry(arbo="1.1", title="Description", info_code="040")

    assert is_pm_title(pm_title)
    assert not is_pm_title(partial_dm)
    assert data_module_entries([pm_title, partial_dm]) == [partial_dm]


def test_direct_extraction_uses_dm_metadata_after_pm_title_rows(
    client, pdf_bytes
) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    _upload_dmrl(client, doc_id, [
        {"Arbo": "1", "Titre": "Présentation"},
        {
            "Arbo": "1.1",
            "DMC": _DMC,
            "Titre": "Description",
            "Type": "Descriptif",
        },
    ])

    with client.stream("POST", f"/api/v1/documents/{doc_id}/extract") as response:
        assert response.status_code == 200
        stream = "".join(response.iter_text())

    assert "event: done" in stream
    xml = client.get(f"/api/v1/documents/{doc_id}/xml").text
    assert 'modelIdentCode="PUMP"' in xml
    assert 'infoCode="040"' in xml
