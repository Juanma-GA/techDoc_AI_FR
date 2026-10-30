"""Parcours API end-to-end : upload -> extract (SSE) -> xml -> override."""

from __future__ import annotations

import json

from lxml import etree


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    cur_event = None
    for line in text.splitlines():
        if line.startswith("event:"):
            cur_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and cur_event:
            payload = line.split(":", 1)[1].strip()
            try:
                events.append((cur_event, json.loads(payload)))
            except json.JSONDecodeError:
                events.append((cur_event, {}))
    return events


def _upload(client, data: bytes, name: str, fmt_field: dict) -> str:
    r = client.post(
        "/api/v1/documents",
        files={"file": (name, data)},
        data=fmt_field,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_upload_rejects_issue_without_local_schema(client, pdf_bytes) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", pdf_bytes)},
        data={"s1000d_issue": "5.0", "context_hint": "mixed"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "BAD_ISSUE"


def test_missing_direct_dmc_is_reported_but_downloadable(client, pdf_bytes) -> None:
    doc_id = _upload(
        client,
        pdf_bytes,
        "manual.pdf",
        {"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    result = _extract(client, doc_id)

    assert not [
        violation for violation in result["violations"]
        if violation["rule"] == "XSD" and violation["severity"] == "error"
    ]
    assert client.get(f"/api/v1/documents/{doc_id}").json()["status"] == "extracted"
    response = client.get(f"/api/v1/documents/{doc_id}/xml")

    assert response.status_code == 200
    assert response.content.startswith(b"<?xml")
    assert response.headers["x-s1000d-xsd-valid"] == "true"
    assert int(response.headers["x-s1000d-missing-fields"]) > 0


def _extract(client, doc_id: str) -> dict:
    with client.stream("POST", f"/api/v1/documents/{doc_id}/extract") as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    events = _parse_sse(body)
    kinds = [e for e, _ in events]
    assert "session" in kinds and "done" in kinds, kinds
    done = [d for e, d in events if e == "done"][-1]
    return done


def test_delete_document_requires_confirmation_and_removes_it(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes, "manual.pdf", {"s1000d_issue": "4.2", "context_hint": "mixed"})

    assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 422
    response = client.delete(f"/api/v1/documents/{doc_id}?confirm_token=confirmed-token")
    assert response.status_code == 200
    assert all(document["id"] != doc_id for document in client.get("/api/v1/documents").json())


def test_pdf_extract_flow(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes, "manual.pdf", {"s1000d_issue": "4.2", "context_hint": "mixed"})
    dmrl = [{
        "DMC": "DMC-PUMP-A-00-00-00-00A-040A-D",
        "Titre": "Description",
        "Type": "Descriptif",
    }]
    response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("DMRL.json", json.dumps(dmrl).encode())},
    )
    assert response.status_code == 200, response.text
    done = _extract(client, doc_id)
    tree = done["tree"]
    kinds = {n["kind"] for n in _walk(tree)}
    assert "admonition" in kinds  # le WARNING a ete detecte
    # XML telechargeable et bien forme.
    r = client.get(f"/api/v1/documents/{doc_id}/xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    etree.fromstring(r.content)


def test_result_persisted_and_retrievable(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes, "m.pdf", {"s1000d_issue": "4.2", "context_hint": "mixed"})
    _extract(client, doc_id)
    # Le resultat est consultable sans relancer l'extraction.
    r = client.get(f"/api/v1/documents/{doc_id}/result")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document_id"] == doc_id
    assert "tree" in body and body["tree"]["children"]


def test_result_before_extract_409(client, pdf_bytes) -> None:
    doc_id = _upload(client, pdf_bytes, "m.pdf", {"s1000d_issue": "4.2", "context_hint": "mixed"})
    r = client.get(f"/api/v1/documents/{doc_id}/result")
    assert r.status_code == 409


def test_docx_extract_flow(client, docx_bytes) -> None:
    doc_id = _upload(client, docx_bytes, "manual.docx", {"s1000d_issue": "4.2", "context_hint": "mixed"})
    dmrl = [{
        "DMC": "DMC-PUMP-A-00-00-00-00A-040A-D",
        "Titre": "Description",
        "Type": "Descriptif",
    }]
    response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("DMRL.json", json.dumps(dmrl).encode())},
    )
    assert response.status_code == 200, response.text
    done = _extract(client, doc_id)
    xml_response = client.get(f"/api/v1/documents/{doc_id}/xml")
    assert xml_response.status_code == 200, xml_response.text
    xml = xml_response.text
    assert "randomList" in xml  # les puces -> randomList en descriptif


def test_invalid_node_override_is_downloadable_with_xsd_warning(client, docx_bytes) -> None:
    doc_id = _upload(client, docx_bytes, "m.docx", {"s1000d_issue": "4.2", "context_hint": "descriptive"})
    dmrl = [{
        "DMC": "DMC-PUMP-A-00-00-00-00A-040A-D",
        "Titre": "Description",
        "Type": "Descriptif",
    }]
    response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("DMRL.json", json.dumps(dmrl).encode())},
    )
    assert response.status_code == 200, response.text
    done = _extract(client, doc_id)
    # Force un paragraphe descriptif en proceduralStep (revue humaine).
    para = next((n for n in _walk(done["tree"]) if n["kind"] == "paragraph"), None)
    assert para is not None
    r = client.patch(
        f"/api/v1/documents/{doc_id}/nodes/{para['id']}",
        json={"element": "proceduralStep"},
    )
    assert r.status_code == 200, r.text
    xsd_issues = [violation for violation in r.json()["violations"] if violation["rule"] == "XSD"]
    assert any("proceduralStep" in violation["message"] for violation in xsd_issues)
    xml_response = client.get(f"/api/v1/documents/{doc_id}/xml")
    assert xml_response.status_code == 200
    assert xml_response.headers["x-s1000d-xsd-valid"] == "false"
    assert "proceduralStep" not in xml_response.text


def test_blank_pdf_rejected(client) -> None:
    import fitz

    doc = fitz.open()
    doc.new_page()  # page vide, aucune couche texte
    data = doc.tobytes()
    doc.close()
    doc_id = _upload(client, data, "blank.pdf", {"s1000d_issue": "4.2", "context_hint": "mixed"})
    with client.stream("POST", f"/api/v1/documents/{doc_id}/extract") as r:
        body = "".join(r.iter_text())
    events = _parse_sse(body)
    assert any(e == "error" and d.get("code") == "EMPTY_SOURCE" for e, d in events), events


def _walk(node: dict) -> list[dict]:
    out = [node]
    for c in node.get("children", []):
        out.extend(_walk(c))
    return out
