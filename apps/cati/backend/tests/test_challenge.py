"""Tests - controle LLM (diff pur) + route challenge (gracieux si LLM off)."""

from __future__ import annotations

from app.core.challenge import diff_items, run_challenge


def _item(fig, c="", i="", f="", qty=""):
    return {"fig": fig, "description": f"d{fig}", "ref_client": c, "ref_interne": i,
            "ref_fournisseur": f, "qty": qty}


def test_diff_all_ok_when_identical() -> None:
    det = [_item("10A", "C1", "I1", "F1", "1"), _item("20A", "C2", "I2", "F2", "3")]
    report = diff_items(det, list(det))
    assert report["status"] == "done"
    assert report["summary"]["ok"] == 2
    assert report["summary"]["clean"] is True


def test_diff_flags_field_mismatch() -> None:
    det = [_item("10A", "C1", "I1", "F1", "1")]
    llm = [_item("10A", "C1", "I1", "F1", "2")]  # qty differe
    report = diff_items(det, llm)
    assert report["summary"]["warning"] == 1
    assert report["summary"]["clean"] is False
    row = report["rows"][0]
    assert row["verdict"] == "warning"
    assert row["issues"][0]["field"] == "qty"
    assert row["issues"][0]["deterministic"] == "1"
    assert row["issues"][0]["llm"] == "2"


def test_diff_missing_and_extra() -> None:
    det = [_item("10A", "C1", "I1", "F1", "1")]        # 10A absent cote LLM -> extra
    llm = [_item("20A", "C2", "I2", "F2", "2")]        # 20A absent cote det -> missing
    report = diff_items(det, llm)
    assert report["summary"]["extra"] == 1
    assert report["summary"]["missing"] == 1
    verdicts = {r["fig"]: r["verdict"] for r in report["rows"]}
    assert verdicts["10A"] == "extra"
    assert verdicts["20A"] == "missing"


def test_run_challenge_skips_without_llm() -> None:
    report = run_challenge("unused.pdf", [_item("10A")], mistral=None)
    assert report["status"] == "skipped"
    assert report["reason"] == "LLM desactive"


# ---- route ----------------------------------------------------------------


def _upload(client, pdf_bytes: bytes) -> str:
    resp = client.post("/api/v1/documents", files=[("files", ("plan.pdf", pdf_bytes, "application/pdf"))])
    return resp.json()["results"][0]["document_id"]


def test_challenge_route_skipped_when_llm_off(client, cati_pdf_bytes) -> None:
    doc_id = _upload(client, cati_pdf_bytes)
    # LLM non configure en test -> challenge saute proprement (pas de 5xx).
    resp = client.get(f"/api/v1/documents/{doc_id}/challenge")
    assert resp.status_code == 200
    assert resp.json()["status"] == "skipped"

    posted = client.post(f"/api/v1/documents/{doc_id}/challenge")
    assert posted.status_code == 200
    assert posted.json()["status"] == "skipped"


def test_challenge_route_diffs_when_llm_available(client, cati_pdf_bytes, monkeypatch) -> None:
    doc_id = _upload(client, cati_pdf_bytes)

    # Simule un LLM dispo + une relecture qui differe sur ref_client de 10A
    # (le deterministe a C1 pour 10A ; on renvoie C999 cote LLM).
    monkeypatch.setattr("app.api.documents._mistral_or_none", lambda db: object())
    monkeypatch.setattr(
        "app.parsers.pdf_table.llm_reextract",
        lambda path, mistral: [
            {"fig": "10A", "ref_client": "C999", "ref_interne": "I1", "ref_fournisseur": "F1"},
            {"fig": "20A", "ref_client": "C2", "ref_interne": "I2", "ref_fournisseur": "F2"},
        ],
    )

    resp = client.post(f"/api/v1/documents/{doc_id}/challenge")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["summary"]["total"] >= 2
    # La ligne 10A doit remonter un ecart sur ref_client (C1 vs C999).
    row10 = next(r for r in body["rows"] if r["fig"] == "10A")
    assert row10["verdict"] == "warning"
    assert any(iss["field"] == "ref_client" for iss in row10["issues"])
