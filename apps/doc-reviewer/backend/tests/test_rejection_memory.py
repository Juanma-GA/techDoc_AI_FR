"""Memoire de rejet : une anomalie rejetee n'est plus re-signalee a la ré-analyse."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _upload(client: TestClient, sample_pdf_bytes: bytes) -> str:
    resp = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    document_id = resp.json()["id"]
    context = client.patch(
        f"/api/v1/documents/{document_id}",
        json={
            "meta_revision_date": "JUL 27/26",
            "meta_cmm_number": "79-30-02",
            "meta_first_issue_date": "JUL 1966",
            "meta_revision_number": "Rev. 01",
            "document_language": "en",
        },
    )
    assert context.status_code == 200, context.text
    return document_id


def _analyze(client: TestClient, doc_id: str) -> bytes:
    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze") as stream:
        assert stream.status_code == 200
        return b"".join(stream.iter_bytes())


def test_rejected_finding_is_suppressed_on_reanalyze(
    client: TestClient, sample_pdf_bytes: bytes
) -> None:
    doc_id = _upload(client, sample_pdf_bytes)
    _analyze(client, doc_id)

    rows = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    assert rows, "au moins une suggestion au premier passage"
    victim = next((row for row in rows if row["original_text"]), None)
    assert victim is not None, "une suggestion avec texte source est requise"

    # Rejet + motif libre (corpus-agent-style).
    patch = client.patch(
        f"/api/v1/suggestions/{victim['id']}",
        json={"status": "rejected", "feedback": "faux positif"},
    )
    assert patch.status_code == 200
    assert patch.json()["feedback"] == "faux positif"

    body = _analyze(client, doc_id)
    assert b"suppressed_rejected" in body

    after = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    # La ligne rejetee persiste (avec son motif) ...
    rejected = [r for r in after if r["status"] == "rejected"]
    assert any(r["feedback"] == "faux positif" for r in rejected)
    # ... et aucune re-detection ouverte ne reprend sa signature.
    sig = (victim["rule_code"], victim["original_text"])
    reopened = [
        r for r in after
        if r["status"] == "open" and (r["rule_code"], r["original_text"]) == sig
    ]
    assert reopened == []


def test_done_event_reports_suppressed_count(
    client: TestClient, sample_pdf_bytes: bytes
) -> None:
    doc_id = _upload(client, sample_pdf_bytes)
    _analyze(client, doc_id)
    rows = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    victim = next((row for row in rows if row["original_text"]), None)
    assert victim is not None, "une suggestion avec texte source est requise"
    rejection = client.patch(
        f"/api/v1/suggestions/{victim['id']}",
        json={"status": "rejected", "feedback": "x"},
    )
    assert rejection.status_code == 200
    body = _analyze(client, doc_id).decode("utf-8", "replace")
    # Recupere la charge JSON de l'event `done`.
    done_payloads = [
        line[len("data: "):]
        for line in body.splitlines()
        if line.startswith("data: ") and "suppressed_rejected" in line
    ]
    assert done_payloads
    parsed = json.loads(done_payloads[-1])
    assert parsed["suppressed_rejected"] >= 1
