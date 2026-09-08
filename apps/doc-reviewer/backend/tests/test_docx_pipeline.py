"""Pipeline Word natif (dual-mode) : upload .docx -> analyse -> apply -> export
.docx corrige. Verifie le round-trip complet sans conversion PDF."""

from __future__ import annotations

import io

from docx import Document as Docx
from fastapi.testclient import TestClient


def _docx_bytes(text: str) -> bytes:
    d = Docx()
    d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _ste100_version_id(client: TestClient) -> str:
    standards = client.get("/api/v1/standards").json()
    for std in standards:
        if std["code"] == "ASD-STE100":
            return std["versions"][0]["id"]
    raise AssertionError("ASD-STE100 seed introuvable")


def test_docx_upload_analyze_apply_export(client: TestClient) -> None:
    sv_id = _ste100_version_id(client)
    data = _docx_bytes("You must utilize the special tool before the check.")

    # 1. Upload : le format d'entree selectionne automatiquement le mode natif.
    up = client.post(
        f"/api/v1/documents?standard_version_ids={sv_id}",
        files={
            "file": (
                "manual.docx",
                data,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert up.status_code == 201, up.text
    doc = up.json()
    assert doc["source_format"] == "docx"
    assert doc["convert_engine"] == "docx-native"
    doc_id = doc["id"]

    # Vue blocs disponible + zones semantiques (Phase 2).
    blocks = client.get(f"/api/v1/documents/{doc_id}/blocks").json()["blocks"]
    assert any("utilize" in b["text"] for b in blocks)
    assert all("semantic_zone" in b and "revised" in b for b in blocks)

    # 2. Analyse (SSE).
    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze") as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())
    assert b"done" in body

    # 3. La regle STE_VOCAB_NON_APPROVED (term_replace utilize->use) doit sortir,
    #    localisee par target_id (bloc docx), pas par bbox.
    sugs = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    vocab = [s for s in sugs if s["rule_code"] == "STE_VOCAB_NON_APPROVED"]
    assert vocab, f"attendu STE_VOCAB_NON_APPROVED, obtenu {[s['rule_code'] for s in sugs]}"
    target = vocab[0]
    assert target["target_id"] and target["target_id"].startswith("dp")
    assert target["original_text"] == "utilize"
    assert target["proposed_text"] == "use"

    # 4. Apply -> nouvelle version docx.
    ap = client.post(f"/api/v1/suggestions/{target['id']}/apply")
    assert ap.status_code == 200, ap.text
    assert ap.json()["new_version"] == 1

    # 5. Export : le .docx corrige contient "use", plus "utilize".
    exp = client.get(f"/api/v1/documents/{doc_id}/export")
    assert exp.status_code == 200
    assert exp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    corrected = Docx(io.BytesIO(exp.content))
    full = "\n".join(p.text for p in corrected.paragraphs)
    assert "use the special tool" in full
    assert "utilize" not in full


def test_docx_undo_restores_original(client: TestClient) -> None:
    """Phase 2 : l'undo (revert) d'une correction docx restaure le .docx precedent."""
    sv_id = _ste100_version_id(client)
    data = _docx_bytes("You must utilize the special tool.")
    up = client.post(
        f"/api/v1/documents?standard_version_ids={sv_id}",
        files={"file": ("m.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    doc_id = up.json()["id"]
    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze") as s:
        b"".join(s.iter_bytes())
    sug = [x for x in client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
           if x["rule_code"] == "STE_VOCAB_NON_APPROVED"][0]

    assert client.post(f"/api/v1/suggestions/{sug['id']}/apply").status_code == 200
    # apres apply : version 1, "utilize" remplace.
    corrected = Docx(io.BytesIO(client.get(f"/api/v1/documents/{doc_id}/export").content))
    assert "utilize" not in "\n".join(p.text for p in corrected.paragraphs)

    # undo -> revient a la version 0.
    rev = client.post(f"/api/v1/suggestions/{sug['id']}/revert")
    assert rev.status_code == 200, rev.text
    assert rev.json()["new_version"] == 0
    restored = Docx(io.BytesIO(client.get(f"/api/v1/documents/{doc_id}/export").content))
    assert "utilize" in "\n".join(p.text for p in restored.paragraphs)


def test_docx_upload_selects_working_format_automatically(client: TestClient) -> None:
    data = _docx_bytes("A native Word document")
    up = client.post(
        "/api/v1/documents",
        files={"file": ("automatic.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert up.status_code == 201, up.text
    document = up.json()
    assert document["source_format"] == "docx"
    assert document["working_format"] == "docx"
    exports = client.get(f"/api/v1/documents/{document['id']}/exports")
    assert exports.status_code == 200
    assert {item["format"] for item in exports.json()["available"]} == {"docx", "pdf"}
