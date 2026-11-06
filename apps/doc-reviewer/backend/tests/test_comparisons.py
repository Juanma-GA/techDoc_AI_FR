from __future__ import annotations

import json

import fitz
from fastapi.testclient import TestClient

from app.core.errors import AppError


def _pdf(*lines: str) -> bytes:
    document = fitz.open()
    page = document.new_page(width=500, height=700)
    for index, line in enumerate(lines):
        page.insert_text((50, 70 + index * 24), line, fontsize=12)
    content = document.tobytes()
    document.close()
    return content


def _multipage_pdf(pages: list[str]) -> bytes:
    document = fitz.open()
    for page_text in pages:
        page = document.new_page(width=500, height=700)
        page.insert_text((50, 70), page_text, fontsize=12)
    content = document.tobytes()
    document.close()
    return content


def _create_comparison(client: TestClient, docs: list[tuple[str, bytes]]) -> dict:
    response = client.post(
        "/api/v1/comparisons",
        data={"reference_index": "0"},
        files=[("files", (filename, content, "application/pdf")) for filename, content in docs],
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_list_and_resume_comparison(client: TestClient) -> None:
    result = _create_comparison(
        client,
        [
            ("reference.pdf", _pdf("Stable requirement", "Removed sentence")),
            ("revision.pdf", _pdf("Stable requirement", "Added sentence")),
        ],
    )

    pair = result["report"]["comparisons"][0]
    assert pair["added_count"] == 1
    assert pair["removed_count"] == 1
    assert {change["text"] for change in pair["changes"]} == {
        "Removed sentence",
        "Added sentence",
    }

    listed = client.get("/api/v1/comparisons")
    assert listed.status_code == 200
    assert result["id"] in {item["id"] for item in listed.json()}

    resumed = client.get(f"/api/v1/comparisons/{result['id']}")
    assert resumed.status_code == 200
    assert resumed.json()["report"] == result["report"]


def test_rejects_pdf_without_extractable_text(client: TestClient) -> None:
    blank = fitz.open()
    blank.new_page()
    blank_pdf = blank.tobytes()
    blank.close()
    response = client.post(
        "/api/v1/comparisons",
        data={"reference_index": "0"},
        files=[
            ("files", ("blank.pdf", blank_pdf, "application/pdf")),
            ("files", ("text.pdf", _pdf("Text layer"), "application/pdf")),
        ],
    )
    assert response.status_code == 422
    assert response.json()["code"] == "PDF_NO_TEXT_LAYER"


def test_export_single_pdf_and_comment_changes(client: TestClient) -> None:
    result = _create_comparison(
        client,
        [
            ("reference.pdf", _pdf("The pump assembly follows procedure version 1120.")),
            ("revision.pdf", _pdf("The pump assembly follows procedure version 1180.")),
        ],
    )

    response = client.get(f"/api/v1/comparisons/{result['id']}/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    annotated = fitz.open(stream=response.content, filetype="pdf")
    assert annotated.page_count == 1
    annotations = list(annotated[0].annots() or [])
    assert annotations
    assert "version 1120" in annotated[0].get_text()
    assert "version 1180" not in annotated[0].get_text()
    assert any("revision.pdf" in annotation.info["title"] for annotation in annotations)
    assert any(
        "version 1120" in annotation.info["content"]
        and "version 1180" in annotation.info["content"]
        for annotation in annotations
    )
    annotated.close()

    individual = client.get(f"/api/v1/comparisons/{result['id']}/export/1?language=en")
    assert individual.status_code == 200
    assert individual.headers["content-type"].startswith("application/pdf")


def test_export_added_text_as_comment_on_reference_pdf(client: TestClient) -> None:
    reference_text = (
        "The maintenance procedure requires inspection of the complete pump assembly."
    )
    result = _create_comparison(
        client,
        [
            ("reference.pdf", _pdf(reference_text)),
            ("revision.pdf", _pdf(reference_text, "New inspection warning.")),
        ],
    )

    response = client.get(f"/api/v1/comparisons/{result['id']}/export")
    assert response.status_code == 200
    annotated = fitz.open(stream=response.content, filetype="pdf")
    assert annotated.page_count == 1
    page = annotated.load_page(0)
    assert reference_text in page.get_text()
    assert "New inspection warning." not in page.get_text()
    annotations = list(page.annots() or [])
    assert any(
        annotation.type[0] == fitz.PDF_ANNOT_TEXT
        and "New inspection warning." in annotation.info["content"]
        and "revision.pdf" in annotation.info["title"]
        for annotation in annotations
    )
    annotated.close()


def test_export_many_differences_on_reference_pdf_and_delete_saved_comparison(
    client: TestClient,
) -> None:
    result = _create_comparison(
        client,
        [
            ("reference.pdf", _pdf("Reference line revision 1")),
            ("revision-a.pdf", _pdf("Reference line revision 2A")),
            ("revision-b.pdf", _pdf("Reference line revision 3B")),
        ],
    )

    export_response = client.get(f"/api/v1/comparisons/{result['id']}/export")
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("application/pdf")
    reference_pdf = fitz.open(stream=export_response.content, filetype="pdf")
    assert reference_pdf.page_count == 1
    assert "Reference line revision 1" in reference_pdf[0].get_text()
    assert "revision 2A" not in reference_pdf[0].get_text()
    annotations = list(reference_pdf[0].annots() or [])
    comments = [annotation.info["content"] for annotation in annotations]
    assert any("revision-a.pdf" in annotation.info["title"] for annotation in annotations)
    assert any("revision-b.pdf" in annotation.info["title"] for annotation in annotations)
    assert any("revision 2A" in comment for comment in comments)
    assert any("revision 3B" in comment for comment in comments)
    reference_pdf.close()

    item_export = client.get(f"/api/v1/comparisons/{result['id']}/export/2")
    assert item_export.status_code == 200
    individual_pdf = fitz.open(stream=item_export.content, filetype="pdf")
    assert individual_pdf.page_count == 1
    assert "Reference line revision 1" in individual_pdf[0].get_text()
    individual_annotations = list(individual_pdf[0].annots() or [])
    assert any("revision-b.pdf" in annotation.info["title"] for annotation in individual_annotations)
    assert all("revision-a.pdf" not in annotation.info["title"] for annotation in individual_annotations)
    individual_pdf.close()
    deleted = client.delete(f"/api/v1/comparisons/{result['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/comparisons/{result['id']}").status_code == 404


def test_synthesis_is_persisted_and_disabled_state_is_explicit(
    client: TestClient,
    monkeypatch,
) -> None:
    result = _create_comparison(
        client,
        [("reference.pdf", _pdf("Old line")), ("revision.pdf", _pdf("New line"))],
    )
    fake_summary = {
        "summary": "The revision changes one requirement.",
        "key_changes": ["One line was added.", "One line was removed."],
        "impact": "Review the updated requirement.",
    }
    monkeypatch.setattr(
        "app.api.comparison_synthesis.call_chat",
        lambda *_args, **_kwargs: json.dumps(fake_summary),
    )
    synthesized = client.post(
        f"/api/v1/comparisons/{result['id']}/synthesis",
        json={"language": "en"},
    )
    assert synthesized.status_code == 200
    assert synthesized.json()["ai_status"] == "completed"
    assert synthesized.json()["ai_summary"]["summary"] == fake_summary["summary"]
    assert client.get(f"/api/v1/comparisons/{result['id']}").json()["ai_summary"] == fake_summary

    def disabled(*_args, **_kwargs):
        raise AppError("LLM_DISABLED", "disabled", status_code=400)

    monkeypatch.setattr("app.api.comparison_synthesis.call_chat", disabled)
    unavailable = client.post(
        f"/api/v1/comparisons/{result['id']}/synthesis",
        json={"language": "fr"},
    )
    assert unavailable.status_code == 200
    assert unavailable.json()["ai_status"] == "disabled"
    assert unavailable.json()["ai_summary"] is None


def test_synthesis_prompt_lists_unmatched_pages_without_their_text(
    client: TestClient,
    monkeypatch,
) -> None:
    result = _create_comparison(
        client,
        [
            (
                "reference.pdf",
                _multipage_pdf(
                    ["Shared first page", "Reference-only private text", "Shared last page"]
                ),
            ),
            (
                "revision.pdf",
                _multipage_pdf(
                    ["Shared first page", "Shared last page", "Revision-only private text"]
                ),
            ),
        ],
    )
    comparison = result["report"]["comparisons"][0]
    assert comparison["changes"] == []
    assert {row["status"] for row in comparison["page_alignment"]} >= {
        "reference_only",
        "comparison_only",
    }

    captured: dict[str, str] = {}

    def capture_prompt(_db, system: str, prompt: str, **_kwargs) -> str:
        captured["system"] = system
        captured["prompt"] = prompt
        return json.dumps(
            {"summary": "Deux pages sont sans correspondance.", "key_changes": [], "impact": ""}
        )

    monkeypatch.setattr("app.api.comparison_synthesis.call_chat", capture_prompt)
    synthesized = client.post(
        f"/api/v1/comparisons/{result['id']}/synthesis",
        json={"language": "fr"},
    )
    assert synthesized.status_code == 200, synthesized.text
    assert "pages présentes dans la référence mais absentes de ce document : 2" in captured["prompt"]
    assert "pages présentes dans ce document mais absentes de la référence : 3" in captured["prompt"]
    assert "Reference-only private text" not in captured["prompt"]
    assert "Revision-only private text" not in captured["prompt"]
    assert "pages sans correspondance" in captured["system"]
