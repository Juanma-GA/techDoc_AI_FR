"""Tests synthetiques de detection et decoupage du PDF."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.config import settings
from app.core.pdf_cut import _start_page_after_tables_list, detect_start_pages
from app.core.pdf_cut_scoring import dmrl_data_module_titles, dmrl_scoring_title
from app.core.pdf_cut_scoring import score_page as _score_page


def _upload(client, data: bytes) -> str:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", data)},
        data={"s1000d_issue": "4.2", "context_hint": "mixed"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_score_penalizes_table_of_contents() -> None:
    toc = "Sommaire\n1 Description generale ........ 3\n2 Removal procedure ........ 8"
    chapter = (
        "Description generale\n"
        "Le systeme hydraulique fournit la pression aux actionneurs et permet le fonctionnement "
        "regulier des equipements. Le fluide circule dans le circuit pour alimenter les organes de "
        "commande, dissiper la chaleur et maintenir les performances prevues. Les controles periodiques "
        "verifient l'etat des conduites, des raccords et des filtres afin de garantir la fiabilite du "
        "systeme.\n"
    )
    toc_score, toc_reasons = _score_page(toc, "Description generale")
    chapter_score, chapter_reasons = _score_page(chapter, "Description generale")

    assert "toc_like_lines" in toc_reasons
    assert "text_density" in chapter_reasons
    assert chapter_score > toc_score


def test_score_recognizes_numbered_section_headings_but_not_toc_entries() -> None:
    section = (
        "1.2 Hydraulic system\n"
        "The system supplies pressure to the actuators and supports normal operation."
    )
    _, section_reasons = _score_page(section, "")
    toc = "1.2 Hydraulic system ........ 5\n1.3 Pump assembly ........ 8"
    _, toc_reasons = _score_page(toc, "")

    assert "numbered_section" in section_reasons
    assert "numbered_section" not in toc_reasons


def test_score_weights_dmrl_title_and_section_number_on_same_line() -> None:
    same_line_score, reasons = _score_page("1.2 Hydraulic system", "Hydraulic system")
    separate_lines_score, _ = _score_page("1.2\nHydraulic system", "Hydraulic system")

    assert "numbered_section" in reasons
    assert same_line_score > separate_lines_score


def test_first_dm_title_skips_publication_only_rows_for_scoring() -> None:
    dmrl_json = json.dumps([
        {
            "arbo": "1",
            "dmc": "DMC-PUMP-A-00-00-00-00A-039A-D",
            "title": "Earlier DM",
        },
        {"arbo": "2", "title": "Title 1"},
        {"arbo": "2.1", "title": "TITRE XXXXXXXX"},
        {"arbo": "2.2", "title": "Partial DM metadata", "info_code": "040"},
        {
            "arbo": "2.3",
            "dmc": "DMC-PUMP-A-00-00-00-00A-040A-D",
            "title": "Hydraulic system",
        },
    ])

    assert dmrl_scoring_title(dmrl_json) == "Hydraulic system"
    assert dmrl_data_module_titles(dmrl_json) == [
        "Hydraulic system",
        "Earlier DM",
        "Partial DM metadata",
    ]


def test_start_page_advances_past_empty_and_blank_pages(tmp_path) -> None:
    import fitz

    pdf_path = tmp_path / "empty-pages-before-content.pdf"
    pdf = fitz.open()
    pdf.new_page()
    pdf.new_page().insert_text((72, 72), "PAGE INTENTIONALLY LEFT BLANK")
    pdf.new_page().insert_text((72, 72), "Manual body begins.")
    pdf.save(str(pdf_path))
    pdf.close()

    document = SimpleNamespace(
        source_format="pdf",
        storage_path=str(pdf_path),
        dmrl_json=json.dumps([
            {"arbo": "1", "title": "Title 1"},
            {"arbo": "1.1", "title": "TITRE XXXXXXXX"},
            {
                "arbo": "1.2",
                "dmc": "DMC-PUMP-A-00-00-00-00A-040A-D",
                "title": "Hydraulic system",
            },
        ]),
    )

    candidates = detect_start_pages(document)

    assert candidates[0]["page"] == 3
    assert "advanced_past_blank_page" in candidates[0]["reasons"]


def test_after_tables_list_hint_uses_first_nonblank_page() -> None:
    assert _start_page_after_tables_list([
        "LIST OF TABLES",
        "First content page",
        "Following page",
    ]) == 2


def test_selected_dm_title_changes_candidate_scoring(tmp_path) -> None:
    import fitz

    pdf_path = tmp_path / "select-first-dm-title.pdf"
    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), "Hydraulic system")
    pdf.new_page().insert_text((72, 72), "Pump assembly")
    pdf.save(str(pdf_path))
    pdf.close()

    document = SimpleNamespace(
        source_format="pdf",
        storage_path=str(pdf_path),
        dmrl_json=json.dumps([
            {
                "dmc": "DMC-PUMP-A-00-00-00-00A-040A-D",
                "title": "Hydraulic system",
            },
            {
                "dmc": "DMC-PUMP-A-00-00-00-00A-041A-D",
                "title": "Pump assembly",
            },
        ]),
    )

    assert detect_start_pages(document)[0]["page"] == 1
    assert detect_start_pages(document, "Pump assembly")[0]["page"] == 2


def test_partial_first_dm_title_outranks_a_generic_heading_on_the_next_page(tmp_path) -> None:
    import fitz

    pdf_path = tmp_path / "dmrl-title-before-following-heading.pdf"
    pdf = fitz.open()
    first_page = pdf.new_page()
    first_page.insert_text((72, 72), "This page introduces the Terminologie entry.")
    for index in range(1, 16):
        first_page.insert_text(
            (72, 72 + 16 * index),
            "Background terminology and system context before the first numbered chapter.",
        )
    second_page = pdf.new_page()
    second_page.insert_text((72, 72), "1.1 First numbered section")
    for index in range(1, 16):
        second_page.insert_text(
            (72, 72 + 16 * index),
            "Detailed section text describes equipment, operation and maintenance steps.",
        )
    pdf.save(str(pdf_path))
    pdf.close()

    document = SimpleNamespace(
        source_format="pdf",
        storage_path=str(pdf_path),
        dmrl_json=json.dumps([{
            "dmc": "DMC-PUMP-A-00-00-00-00A-040A-D",
            "title": "Terminologie",
        }]),
    )

    candidates = detect_start_pages(document)

    assert candidates[0]["page"] == 1
    assert "dmrl_title_contains" in candidates[0]["reasons"]


def test_selected_title_score_outranks_after_tables_list_hint(tmp_path) -> None:
    import fitz

    pdf_path = tmp_path / "selected-title-over-list-boundary.pdf"
    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), "LIST OF TABLES")
    pdf.new_page().insert_text((72, 72), "General information")
    pdf.new_page().insert_text((72, 72), "Hydraulic system")
    pdf.save(str(pdf_path))
    pdf.close()

    document = SimpleNamespace(
        source_format="pdf",
        storage_path=str(pdf_path),
        dmrl_json=json.dumps([
            {
                "dmc": "DMC-PUMP-A-00-00-00-00A-040A-D",
                "title": "Hydraulic system",
            },
        ]),
    )

    candidates = detect_start_pages(document, "Hydraulic system")

    assert candidates[0]["page"] == 3
    assert "dmrl_title_exact" in candidates[0]["reasons"]


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
    assert detection.json()["dmrl_titles"] == ["Description"]

    selected_detection = client.post(
        f"/api/v1/documents/{doc_id}/pdf-cut/detect",
        json={"title": "Description"},
    )
    assert selected_detection.status_code == 200
    assert selected_detection.json()["candidates"][0]["page"] == 1

    invalid_title = client.post(
        f"/api/v1/documents/{doc_id}/pdf-cut/detect",
        json={"title": "Not in DMRL"},
    )
    assert invalid_title.status_code == 422

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
