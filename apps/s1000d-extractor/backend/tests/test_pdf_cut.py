"""Tests synthetiques de detection et decoupage du PDF."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.config import settings
from app.core.pdf_cut import _score_page, detect_start_pages


def _upload(client, data: bytes) -> str:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", data)},
        data={"s1000d_issue": "5.0", "context_hint": "mixed"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_score_penalizes_table_of_contents() -> None:
    toc = "Sommaire\n1 Description generale ........ 3\n2 Removal procedure ........ 8"
    chapter = "Description generale\nLe systeme hydraulique fournit la pression aux actionneurs.\n"
    toc_score, toc_reasons = _score_page(toc, "Description generale")
    chapter_score, chapter_reasons = _score_page(chapter, "Description generale")

    assert "toc_like_lines" in toc_reasons
    assert "text_density" in chapter_reasons
    assert chapter_score > toc_score


def test_start_page_skips_table_lists_and_blank_pages(tmp_path) -> None:
    import fitz

    pdf_path = tmp_path / "lists-and-blank-pages.pdf"
    pdf = fitz.open()
    pdf.new_page().insert_text(
        (72, 72),
        "Description\nIntroductory material for the maintenance manual. "
        "This text is deliberately dense enough to score as a candidate.",
    )
    pdf.new_page().insert_text((72, 72), "LIST OF TABLES")
    pdf.new_page().insert_text((72, 72), "LIST OF TABLES (continued)")
    pdf.new_page().insert_text((72, 72), "PAGE INTENTIONALLY LEFT BLANK")
    pdf.new_page().insert_text(
        (72, 72),
        "Title 1\nChapter 1: Hydraulic system description.",
    )
    pdf.new_page().insert_text((72, 72), "Page immediately after Title 1.")
    pdf.save(str(pdf_path))
    pdf.close()

    document = SimpleNamespace(
        source_format="pdf",
        storage_path=str(pdf_path),
        dmrl_json=json.dumps([{"title": "Description"}]),
    )

    candidates = detect_start_pages(document)

    assert candidates[0]["page"] == 5
    assert "after_list_of_tables" in candidates[0]["reasons"]
    assert all("LIST OF TABLES" not in candidate["preview"] for candidate in candidates)


def test_pdf_cut_can_preview_and_confirm_page(client, pdf_bytes_headers, monkeypatch) -> None:
    doc_id = _upload(client, pdf_bytes_headers)
    dmrl = {"DMC": "DMC-TEST-A-00-00-00-00A-040A-D", "Titre": "Description"}
    # Keep the fixture independent from any real user file.
    response = client.post(
        f"/api/v1/documents/{doc_id}/resources/dmrl",
        files={"file": ("dmrl.json", json.dumps([dmrl]).encode(), "application/json")},
    )
    assert response.status_code == 200, response.text

    monkeypatch.setattr(settings, "pdf_cut_requires_validation", True)
    detection = client.post(f"/api/v1/documents/{doc_id}/pdf-cut/detect")
    assert detection.status_code == 200
    assert detection.json()["candidates"]
    assert detection.json()["total_pages"] == 3
    assert detection.json()["default_start_page"] == 1

    preview = client.get(f"/api/v1/documents/{doc_id}/pdf-cut/preview/2")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"

    blocked = client.post(f"/api/v1/documents/{doc_id}/wizard/start", json={"cut_pdf": True})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "PDF_CUT_VALIDATION_REQUIRED"

    confirmed = client.post(
        f"/api/v1/documents/{doc_id}/pdf-cut/confirm",
        json={"start_page": 2, "end_page": 3},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["start_page"] == 2
    assert confirmed.json()["end_page"] == 3
    assert confirmed.json()["page_count"] == 2

    started = client.post(f"/api/v1/documents/{doc_id}/wizard/start", json={"cut_pdf": True})
    assert started.status_code == 200
