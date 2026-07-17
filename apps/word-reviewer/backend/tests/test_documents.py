"""Tests routes documents : upload (single/zip), analyze SSE, suggestions, apply, export."""

from __future__ import annotations

import io
import zipfile

from tests.conftest import DOCX_MIME


def _events(text: str) -> list[str]:
    return [line.split(": ", 1)[1] for line in text.splitlines() if line.startswith("event:")]


def _add_rule(client, **kw):
    payload = {"name": kw.get("name", "rule"), "kind": kw["kind"], "validated": True}
    payload.update(kw)
    return client.post("/api/v1/rules", json=payload).json()


def test_upload_single_and_analyze(client, make_docx):
    # Detection par les regles ATA100 builtin (chapitrage).
    data = make_docx(["Chapter 250 has several parts."], headings=["GENERAL"])
    up = client.post("/api/v1/documents", files={"files": ("t.docx", data, DOCX_MIME)})
    assert up.status_code == 200
    doc_id = up.json()["documents"][0]["id"]

    an = client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    assert an.status_code == 200
    evs = _events(an.text)
    assert evs[0] == "session" and evs[-1] == "done"

    codes = {s["rule_code"] for s in client.get(f"/api/v1/documents/{doc_id}/suggestions").json()}
    assert "ATA_CHAPTER_RANGE" in codes
    assert "ATA_NO_AMBIGUOUS_QUANT" in codes


def test_ata_ref_ignores_phone_flags_real_ref(client, make_docx):
    # Un numero de telephone ne doit PAS declencher ATA_CHAPTER_REF ; une vraie
    # reference pointee, si.
    data = make_docx(["Tel : +33 (0)5 24 44 77 40", "Voir 34.10.42 pour le detail."])
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", data, DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    sugs = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    refs = [s for s in sugs if s["rule_code"] == "ATA_CHAPTER_REF"]
    assert all(s["original_text"] != "24 44 77" for s in refs)  # pas le telephone
    assert any(s["original_text"] == "34.10.42" for s in refs)  # la vraie ref


def test_analyze_streams_progress(client, make_docx, monkeypatch):
    # Avec une regle llm_nl active, l'analyse doit diffuser des events `progress`
    # (avancement en direct) avant les findings.
    from app.core import llm_checks as lc

    class _Fake:
        async def chat(self, messages, **kw):
            return '{"violations":[]}'

    monkeypatch.setattr(lc.MistralClient, "from_db", staticmethod(lambda db: _Fake()))
    client.post("/api/v1/admin/reset/rules")
    client.post("/api/v1/rules", json={"name": "Style ATA", "kind": "llm_nl", "message": "Phrase conforme", "validated": True})
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", make_docx(["Une phrase."]), DOCX_MIME)}
    ).json()["documents"][0]["id"]
    evs = _events(client.post(f"/api/v1/documents/{doc_id}/analyze", json={}).text)
    assert evs[0] == "session" and "progress" in evs and evs[-1] == "done"


def test_doc_accepted_by_extractor():
    # Le .doc est accepte a l'extraction (la conversion en .docx a lieu ensuite).
    from app.core.uploads import extract_uploads

    docs, ignored = extract_uploads([("legacy.doc", b"fakedoc"), ("note.txt", b"x")])
    assert any(name.endswith(".doc") for name, _ in docs)
    assert "note.txt" in ignored


def test_upload_zip_creates_batch(client, make_docx):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.docx", make_docx(["Doc A made by THOMSON."]))
        zf.writestr("b.docx", make_docx(["Doc B normal."]))
        zf.writestr("readme.txt", b"ignored")
    up = client.post("/api/v1/documents", files={"files": ("batch.zip", buf.getvalue(), "application/zip")})
    assert up.status_code == 200
    body = up.json()
    assert len(body["documents"]) == 2
    assert "readme.txt" in body["ignored"]
    assert body["batch_id"]


def test_apply_changes_docx_and_bumps_version(client, make_docx):
    # Une regle custom de remplacement (le client la fournit via sa checklist).
    client.post("/api/v1/admin/reset/rules")
    _add_rule(client, name="Rename SEXTANT", kind="regex_replace", pattern="SEXTANT", replacement="ACME")
    data = make_docx(["Made by SEXTANT division SEXTANT."])
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", data, DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    sug = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    brand = [s for s in sug if s["original_text"] == "SEXTANT"][0]
    res = client.post(f"/api/v1/suggestions/{brand['id']}/apply-group")
    assert res.status_code == 200

    doc = client.get(f"/api/v1/documents/{doc_id}").json()
    assert doc["current_version"] == 1

    from docx import Document

    exported = client.get(f"/api/v1/documents/{doc_id}/export").content
    text = " ".join(p.text for p in Document(io.BytesIO(exported)).paragraphs)
    assert "SEXTANT" not in text
    assert text.count("ACME") == 2


def test_undo_restores_previous_version(client, make_docx):
    client.post("/api/v1/admin/reset/rules")
    _add_rule(client, name="Rename SEXTANT", kind="regex_replace", pattern="SEXTANT", replacement="ACME")
    data = make_docx(["Made by SEXTANT."])
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", data, DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    sug = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    brand = [s for s in sug if s["original_text"] == "SEXTANT"][0]
    client.post(f"/api/v1/suggestions/{brand['id']}/apply")
    assert client.get(f"/api/v1/documents/{doc_id}").json()["current_version"] == 1
    # Contrat front : applied_version expose et aligne sur la version courante
    # (le bouton "Annuler" n'est actif que sur la correction de cette version).
    applied = [s for s in client.get(f"/api/v1/documents/{doc_id}/suggestions").json() if s["id"] == brand["id"]][0]
    assert applied["status"] == "applied" and applied["applied_version"] == 1

    res = client.post(f"/api/v1/suggestions/{brand['id']}/undo")
    assert res.status_code == 200
    # Version restauree + suggestion reouverte.
    assert client.get(f"/api/v1/documents/{doc_id}").json()["current_version"] == 0
    reopened = [s for s in client.get(f"/api/v1/documents/{doc_id}/suggestions").json() if s["id"] == brand["id"]][0]
    assert reopened["status"] == "open"

    from docx import Document

    exported = client.get(f"/api/v1/documents/{doc_id}/export").content
    text = " ".join(p.text for p in Document(io.BytesIO(exported)).paragraphs)
    assert "SEXTANT" in text and "ACME" not in text


def test_undo_without_apply_fails(client, make_docx):
    client.post("/api/v1/admin/reset/rules")
    _add_rule(client, name="Rename SEXTANT", kind="regex_replace", pattern="SEXTANT", replacement="ACME")
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", make_docx(["Made by SEXTANT."]), DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    sug = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    brand = [s for s in sug if s["original_text"] == "SEXTANT"][0]
    assert client.post(f"/api/v1/suggestions/{brand['id']}/undo").status_code == 409


def test_llm_rule_surfaces_in_analysis(client, make_docx, monkeypatch):
    # Une regle llm_nl validee (onglet Standards & Regles) doit produire un finding
    # correctif coherent a l'analyse (passage LLM bout en bout, client simule).
    from app.core import llm_checks as lc

    class _Fake:
        async def chat(self, messages, **kw):
            return '{"violations":[{"r":0,"b":0,"confidence":0.9,"reason":"non conforme","proposed":"Texte corrige."}]}'

    monkeypatch.setattr(lc.MistralClient, "from_db", staticmethod(lambda db: _Fake()))
    client.post("/api/v1/admin/reset/all")
    client.post("/api/v1/admin/reset/rules")
    client.post("/api/v1/rules", json={"name": "Style ATA", "kind": "llm_nl", "message": "Phrase conforme ATA100", "validated": True})
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", make_docx(["Une phrase a corriger."]), DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    sug = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    llm = [s for s in sug if s["rule_kind"] == "custom" and s["proposed_text"]]
    assert llm and llm[0]["proposed_text"] == "Texte corrige."


def test_delete_document(client, make_docx):
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", make_docx(["X."]), DOCX_MIME)}
    ).json()["documents"][0]["id"]
    assert client.get(f"/api/v1/documents/{doc_id}").status_code == 200
    r = client.delete(f"/api/v1/documents/{doc_id}")
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert client.get(f"/api/v1/documents/{doc_id}").status_code == 404


def test_export_zip(client, make_docx):
    ids = []
    for i in range(2):
        d = make_docx([f"Doc {i}."])
        ids.append(
            client.post("/api/v1/documents", files={"files": (f"d{i}.docx", d, DOCX_MIME)}).json()[
                "documents"
            ][0]["id"]
        )
    r = client.post("/api/v1/documents/export-zip", json={"document_ids": ids})
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert len(zf.namelist()) == 2


def test_reject_creates_exclusion(client, make_docx):
    data = make_docx(["This has several parts."])
    doc_id = client.post(
        "/api/v1/documents", files={"files": ("t.docx", data, DOCX_MIME)}
    ).json()["documents"][0]["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    sug = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    amb = [s for s in sug if s["rule_code"] == "ATA_NO_AMBIGUOUS_QUANT"][0]
    client.patch(f"/api/v1/suggestions/{amb['id']}", json={"status": "rejected"})
    # Re-analyse : le finding rejete ne doit pas reapparaitre.
    client.post(f"/api/v1/documents/{doc_id}/analyze", json={})
    sug2 = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    assert not any(
        s["rule_code"] == "ATA_NO_AMBIGUOUS_QUANT" and s["original_text"] == "several" for s in sug2
    )
