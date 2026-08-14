"""Routes ressources (DMRL / CIR / regles client) et effet sur l'assistant."""

from __future__ import annotations

import json

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


def _upload_doc(client, data: bytes) -> str:
    r = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", data)},
        data={"s1000d_issue": "5.0", "context_hint": "mixed"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


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
    assert [d["title"] for d in state["dms"]] == ["Removal Procedure"]
    assert state["dms"][0]["dm_type"] == "ipd"


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
    assert [e.findtext("pmEntryTitle") for e in root.findall("./content/pmEntry")] == [
        "Description", "Removal Procedure"
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
    assert state["resources"] == {"dmrl_count": 0, "has_cir": True, "has_brex_rules": True}


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
