from __future__ import annotations

import json
import uuid

import fitz
from fastapi.testclient import TestClient

from app.db.comparison_models import DocumentComparison
from app.db.session import SessionLocal


def _multipage_pdf(pages: list[str]) -> bytes:
    document = fitz.open()
    for page_text in pages:
        page = document.new_page(width=500, height=700)
        page.insert_text((50, 70), page_text, fontsize=12)
    content = document.tobytes()
    document.close()
    return content


def _create(client: TestClient, reference: bytes, comparison: bytes) -> dict:
    response = client.post(
        "/api/v1/comparisons",
        data={"reference_index": "0"},
        files=[
            ("files", ("reference.pdf", reference, "application/pdf")),
            ("files", ("revision.pdf", comparison, "application/pdf")),
        ],
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_page_text_alignment_keeps_inserted_pages_as_slots_and_renders_png(
    client: TestClient,
) -> None:
    result = _create(
        client,
        _multipage_pdf(["Page one stays", "Page two stays"]),
        _multipage_pdf(["Page one stays", "Inserted page", "Page two stays"]),
    )

    report = result["report"]
    comparison = report["comparisons"][0]
    assert report["schema_version"] == 2
    assert [slot["id"] for slot in report["page_slots"]] == [
        "reference-1",
        "comparison-1-page-2",
        "reference-2",
    ]
    mapped_page_two = next(
        row for row in comparison["page_alignment"] if row["slot_id"] == "reference-2"
    )
    assert mapped_page_two["reference_page"] == 2
    assert mapped_page_two["comparison_page"] == 3
    assert mapped_page_two["status"] == "aligned"
    assert any(row["status"] == "comparison_only" for row in comparison["page_alignment"])

    image = client.get(
        f"/api/v1/comparisons/{result['id']}/documents/1/pages/3.png"
    )
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")
    assert image.content.startswith(b"\x89PNG\r\n\x1a\n")

    missing = client.get(
        f"/api/v1/comparisons/{result['id']}/documents/1/pages/4.png"
    )
    assert missing.status_code == 404


def test_opening_legacy_saved_report_rebuilds_alignment(client: TestClient) -> None:
    result = _create(
        client,
        _multipage_pdf(["Same page"]),
        _multipage_pdf(["Changed page"]),
    )
    comparison_id = uuid.UUID(result["id"])

    with SessionLocal() as db:
        row = db.get(DocumentComparison, comparison_id)
        assert row is not None
        legacy = json.loads(row.report_json)
        legacy.pop("schema_version")
        legacy.pop("page_slots")
        for pair in legacy["comparisons"]:
            pair.pop("page_alignment")
            for change in pair["changes"]:
                change.pop("group_id")
                bbox = change["bbox"]
                change["bbox"] = [bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"]]
        row.report_json = json.dumps(legacy)
        db.commit()

    opened = client.get(f"/api/v1/comparisons/{result['id']}")
    assert opened.status_code == 200
    upgraded = opened.json()["report"]
    assert upgraded["schema_version"] == 2
    assert upgraded["page_slots"]
    assert upgraded["comparisons"][0]["page_alignment"]
    assert upgraded["comparisons"][0]["changes"][0]["group_id"]
    assert isinstance(upgraded["comparisons"][0]["changes"][0]["bbox"], dict)
