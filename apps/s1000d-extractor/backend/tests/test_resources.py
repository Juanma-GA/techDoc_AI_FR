"""Routes ressources (DMRL / CIR / regles client) et effet sur l'assistant."""

from __future__ import annotations

import json
from pathlib import Path

from lxml import etree

_DMRL = [
    {"Arbo": "1", "DMC": "DMC-PUMP-A-00-00-00-00A-040A-D", "Titre": "Description",
     "Type": "Descriptif"},
    {"Arbo": "2", "DMC": "DMC-PUMP-A-00-00-00-00A-520A-D", "Titre": "Removal Procedure",
     "Type": "Procedure"},
]

_CIR = (
    '<?xml version="1.0" encoding="UTF-8"?><commonRepository>'
    '<warning id="WARN-001"><para>Couper l alimentation.</para></warning>'
    "</commonRepository>"
)

_DMRL_WITH_ICN = [{
    "Arbo": "1",
    "DMC": "DMC-PUMP-A-00-00-00-00A-040A-D",
    "Titre": "Description",
    "Type": "Descriptif",
    "ICN": "ICN-WEG-AA0004-00001-A-02.png",
}]


def _upload_doc(client, data: bytes) -> str:
    r = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", data)},
        data={"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    detection = client.post(f"/api/v1/documents/{doc_id}/pdf-cut/detect")
    assert detection.status_code == 200, detection.text
    cut = detection.json()
    if cut["validation_required"]:
        confirmation = client.post(
            f"/api/v1/documents/{doc_id}/pdf-cut/confirm",
            json={
                "start_page": cut["selected_page"] or cut["default_start_page"],
                "end_page": cut["selected_end_page"] or cut["total_pages"],
            },
        )
        assert confirmation.status_code == 200, confirmation.text
    return doc_id


def _upload_resource(client, doc_id: str, kind: str, name: str, payload: bytes):
    return client.post(
        f"/api/v1/documents/{doc_id}/resources/{kind}", files={"file": (name, payload)}
    )


def test_dmrl_upload_drives_the_split(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    r = _upload_resource(client, doc_id, "dmrl", "DMRL.json", json.dumps(_DMRL).encode())
    assert r.status_code == 200, r.text
    assert r.json() == {"kind": "dmrl", "count": 2}

    # Une DMRL chargee insere une etape de validation AVANT le decoupage.
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert state["step"] == "dmrl"
    assert state["steps"] == ["dmrl", "split", "type", "structure", "generate"]
    assert [row["matched"] for row in state["dmrl"]] == [True, True]

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "split"
    assert [d["title"] for d in state["dms"]] == ["Description", "Removal Procedure"]
    # Le type declare dans la DMRL fait foi.
    assert [d["dm_type"] for d in state["dms"]] == ["descriptive", "procedural"]
    assert state["resources"]["dmrl_count"] == 2


def test_document_defaults_to_issue_4_2(client, pdf_bytes) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", pdf_bytes)},
        data={"context_hint": "mixed"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["s1000d_issue"] == "4.2"


def test_migration_input_mapping_persists_last_files(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    dmrl_payload = json.dumps(_DMRL).encode()
    header_payload = b'{"security":{"securityClassification":"04"}}'
    assert _upload_resource(client, doc_id, "dmrl", "client-dmrl.json", dmrl_payload).status_code == 200
    assert _upload_resource(client, doc_id, "dm_header", "client-header.json", header_payload).status_code == 200

    mapping = client.get("/api/v1/migration-inputs")
    assert mapping.status_code == 200, mapping.text
    body = mapping.json()
    assert body["issue"] == "4.2"
    assert body["context_hint"] == "mixed"
    assert body["files"]["document"]["filename"] == "manual.pdf"
    assert body["files"]["dmrl"]["filename"] == "client-dmrl.json"
    assert body["files"]["dm_header"]["filename"] == "client-header.json"

    assert client.get("/api/v1/migration-inputs/document").content == pdf_bytes
    assert client.get("/api/v1/migration-inputs/dmrl").content == dmrl_payload
    assert client.get("/api/v1/migration-inputs/dm_header").content == header_payload


def test_dmrl_icn_renames_image_and_xml_omits_extension(client, pdf_bytes_image) -> None:
    doc_id = _upload_doc(client, pdf_bytes_image)
    _upload_resource(client, doc_id, "dmrl", "DMRL.json", json.dumps(_DMRL_WITH_ICN).encode())

    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/start",
        json={"start_page": 1},
    ).json()
    assert state["dmrl"][0]["icn"] == "ICN-WEG-AA0004-00001-A-02.png"

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    names = client.get(f"/api/v1/documents/{doc_id}/wizard/images").json()
    assert names == ["ICN-WEG-AA0004-00001-A-02.png"]
    image = client.get(f"/api/v1/documents/{doc_id}/wizard/images/{names[0]}")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"

    for payload in ({"types": {}}, {"overrides": []}, {}):
        state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json=payload).json()
    xml = client.get(
        f"/api/v1/documents/{doc_id}/wizard/dm/{state['dms'][0]['dm_id']}/xml"
    ).text
    assert "<!DOCTYPE dmodule [" in xml
    assert (
        '<!ENTITY ICN-WEG-AA0004-00001-A-02 SYSTEM '
        '"ICN-WEG-AA0004-00001-A-02.png" NDATA png>' in xml
    )
    assert 'infoEntityIdent="ICN-WEG-AA0004-00001-A-02"' in xml
    assert 'infoEntityIdent="ICN-WEG-AA0004-00001-A-02.png"' not in xml


def test_existing_dm_without_doctype_is_upgraded_on_download(client, pdf_bytes_image) -> None:
    from app.db.models import Document
    from app.db.session import SessionLocal

    doc_id = _upload_doc(client, pdf_bytes_image)
    response = _upload_resource(
        client, doc_id, "dmrl", "DMRL.json", json.dumps(_DMRL_WITH_ICN).encode()
    )
    assert response.status_code == 200, response.text
    client.post(f"/api/v1/documents/{doc_id}/wizard/start", json={"start_page": 1})
    for payload in ({}, {"types": {}}, {"overrides": []}, {}):
        state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json=payload).json()
    dm_id = state["dms"][0]["dm_id"]

    db = SessionLocal()
    try:
        document = db.get(Document, doc_id)
        dms = json.loads(document.dms_json)
        dms[0]["xml"] = dms[0]["xml"].split("<!DOCTYPE dmodule [", 1)[0] + dms[0]["xml"].split("]>\n", 1)[1]
        document.dms_json = json.dumps(dms, ensure_ascii=False)
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{dm_id}/xml")
    assert response.status_code == 200
    assert "<!DOCTYPE dmodule [" in response.text


def test_dmrl_step_reports_unmatched_entry(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    dmrl = [*_DMRL, {"Arbo": "3", "Titre": "Chapitre absent", "Type": "Descriptif"}]
    _upload_resource(client, doc_id, "dmrl", "DMRL.json", json.dumps(dmrl).encode())
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    rows = state["dmrl"]
    assert rows[2]["matched"] is False and rows[2]["page"] is None
    assert rows[0]["page"] is not None


def test_dmrl_step_edits_before_split(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    _upload_resource(client, doc_id, "dmrl", "DMRL.json", json.dumps(_DMRL).encode())
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")

    url = f"/api/v1/documents/{doc_id}/wizard/update"
    state = client.post(url, json={"op": "rename", "index": 0, "title": "Vue generale"}).json()
    assert state["dmrl"][0]["title"] == "Vue generale"
    state = client.post(url, json={"op": "set_type", "index": 1, "dm_type": "ipd"}).json()
    assert state["dmrl"][1]["dm_type"] == "ipd"
    state = client.post(url, json={"op": "exclude", "index": 0}).json()
    assert [row["title"] for row in state["dmrl"]] == ["Removal Procedure"]

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    # Le contenu qui precede le 1er DM retenu n'est pas jete : il devient un DM
    # marque `is_orphan` (libelle rendu cote UI) que l'humain rattache ou exclut.
    assert [d["is_orphan"] for d in state["dms"]] == [True, False]
    assert state["dms"][1]["title"] == "Removal Procedure"
    assert state["dms"][1]["dm_type"] == "ipd"


def test_wizard_back_returns_to_dmrl_step(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    _upload_resource(client, doc_id, "dmrl", "DMRL.json", json.dumps(_DMRL).encode())
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/back").json()
    assert state["step"] == "dmrl"


def test_without_dmrl_the_wizard_starts_on_split(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert state["step"] == "split"
    assert state["steps"] == ["split", "type", "structure", "generate"]


def test_pmc_endpoint(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    _upload_resource(client, doc_id, "dmrl", "DMRL.json", json.dumps(_DMRL).encode())
    r = client.get(f"/api/v1/documents/{doc_id}/pmc")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    root = etree.fromstring(r.content)
    top = root.findall("./content/pmEntry")
    assert [entry.findtext("pmEntryTitle") for entry in top] == ["Description"]
    assert [entry.findtext("pmEntryTitle") for entry in top[0].findall("./pmEntry")] == [
        "Removal Procedure"
    ]


def test_pmc_without_dmrl_is_409(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    assert client.get(f"/api/v1/documents/{doc_id}/pmc").status_code == 409


def test_resource_format_is_checked(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    assert _upload_resource(client, doc_id, "dmrl", "dmrl.txt", b"x").status_code == 422
    assert _upload_resource(client, doc_id, "inconnu", "x.json", b"{}").status_code == 422
    # Contenu invalide -> refus explicite (pas de 500).
    assert _upload_resource(client, doc_id, "cir", "cir.xml", b"<a><b></a>").status_code == 422


def test_cir_and_brex_rules_upload(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    assert _upload_resource(client, doc_id, "cir", "cir.xml", _CIR.encode()).json()["count"] == 1
    rules = json.dumps({"max_title_levels": 0}).encode()
    assert _upload_resource(client, doc_id, "brex_rules", "rules.json", rules).status_code == 200
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert state["resources"] == {
        "dmrl_count": 0, "has_cir": True, "has_brex_rules": True,
        "has_dm_header": False, "errors": []
    }


def test_client_dm_header_template_is_applied(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    template = {
        "security": {"securityClassification": "04"},
        "responsiblePartnerCompany": {
            "enterpriseCode": "TST",
            "enterpriseName": "TEST COMPANY",
        },
        "originator": {
            "enterpriseCode": "TST",
            "enterpriseName": "TEST COMPANY",
        },
    }
    response = _upload_resource(
        client, doc_id, "dm_header", "header.json", json.dumps(template).encode()
    )
    assert response.status_code == 200, response.text
    response = _upload_resource(
        client, doc_id, "dmrl", "DMRL.json", json.dumps(_DMRL).encode()
    )
    assert response.status_code == 200, response.text
    state = client.post(
        f"/api/v1/documents/{doc_id}/wizard/start", json={"start_page": 1}
    ).json()
    assert state["resources"]["has_dm_header"] is True
    for payload in ({}, {"types": {}}, {"overrides": []}, {}):
        state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json=payload).json()
    xml = client.get(
        f"/api/v1/documents/{doc_id}/wizard/dm/{state['dms'][0]['dm_id']}/xml"
    ).text
    assert 'securityClassification="04"' in xml
    assert "TEST COMPANY" in xml


def test_imported_resource_paths_are_persisted(client, pdf_bytes) -> None:
    from app.db.models import Document
    from app.db.session import SessionLocal

    doc_id = _upload_doc(client, pdf_bytes)
    assert _upload_resource(
        client, doc_id, "dmrl", "client-dmrl.json", json.dumps(_DMRL).encode()
    ).status_code == 200
    assert _upload_resource(
        client, doc_id, "dm_header", "client-header.json", b"{}"
    ).status_code == 200

    db = SessionLocal()
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        assert Path(document.storage_path).exists()
        assert Path(document.dmrl_path).name == f"document_{doc_id}_dmrl.json"
        assert Path(document.dmrl_path).exists()
        assert Path(document.dm_header_path).name == f"document_{doc_id}_dm_header.json"
        assert Path(document.dm_header_path).exists()
    finally:
        db.close()


def test_unreadable_resource_is_reported_not_swallowed(client, pdf_bytes, tmp_path) -> None:
    """Une ressource attachee puis devenue illisible ne doit pas s'afficher comme
    active : l'utilisateur livrerait des DM en croyant ses regles appliquees."""
    from app.db.models import Document
    from app.db.session import SessionLocal

    doc_id = _upload_doc(client, pdf_bytes)
    broken = tmp_path / "rules.json"
    broken.write_text("{ pas du json", encoding="utf-8")
    db = SessionLocal()
    try:
        db.get(Document, doc_id).brex_rules_path = str(broken)
        db.commit()
    finally:
        db.close()

    state = client.post(f"/api/v1/documents/{doc_id}/wizard/start").json()
    assert state["resources"]["has_brex_rules"] is False
    assert state["resources"]["errors"], "l'echec de chargement doit remonter a l'UI"

    for payload in ({}, {"types": {}}, {"overrides": []}, {}):
        state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json=payload).json()
    assert state["step"] == "generate"
    assert all(d["violation_count"] for d in state["dms"])


def test_cir_upload_rejects_external_entities(client, pdf_bytes, tmp_path) -> None:
    """XXE : un CIR qui reference un fichier local ne doit rien exfiltrer."""
    secret = tmp_path / "secret.txt"
    secret.write_text("MOT-DE-PASSE", encoding="utf-8")
    xxe = (
        '<?xml version="1.0"?>'
        f'<!DOCTYPE r [<!ENTITY xxe SYSTEM "file:///{secret.as_posix()}">]>'
        '<commonRepository><warning id="W1">&xxe;</warning></commonRepository>'
    )
    doc_id = _upload_doc(client, pdf_bytes)
    r = _upload_resource(client, doc_id, "cir", "cir.xml", xxe.encode())
    assert r.status_code == 422, "un CIR avec entite externe doit etre refuse"
    assert "MOT-DE-PASSE" not in r.text


def test_client_brex_rules_are_reported_at_generation(client, pdf_bytes) -> None:
    doc_id = _upload_doc(client, pdf_bytes)
    _upload_resource(client, doc_id, "brex_rules", "rules.json",
                     json.dumps({"max_title_levels": 0}).encode())
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"types": {}})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"overrides": []})
    state = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert state["step"] == "generate"
    assert any(d["violation_count"] for d in state["dms"])
