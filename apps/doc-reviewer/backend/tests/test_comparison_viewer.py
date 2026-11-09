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


def _create(
    client: TestClient,
    reference: bytes,
    comparison: bytes,
    page_similarity_threshold: int | None = None,
) -> dict:
    data = {"reference_index": "0"}
    if page_similarity_threshold is not None:
        data["page_similarity_threshold"] = str(page_similarity_threshold)
    response = client.post(
        "/api/v1/comparisons",
        data=data,
        files=[
            ("files", ("reference.pdf", reference, "application/pdf")),
            ("files", ("revision.pdf", comparison, "application/pdf")),
        ],
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_similar_pages_align_after_insertions_and_report_unmatched_pages(
    client: TestClient,
) -> None:
    page_bodies = [
        "Introduction and scope",
        "Hydraulic pump removal instructions",
        "Fuel pressure inspection limits",
        "Electrical harness routing details",
        "Approved engine lubrication fluids",
        "Landing gear actuator adjustment",
        "Rotor blade balance procedure",
        "Cabin panel fastener locations",
        "Emergency lighting circuit tests",
        "Corrosion protection inspection",
    ]
    reference_pages = [
        f"{body} printed page {page}"
        for page, body in enumerate(page_bodies, start=1)
    ]
    comparison_pages = [
        reference_pages[0],
        "Inserted appendix for calibration notes",
        "Inserted appendix for terminology",
        *reference_pages[1:6],
        f"{page_bodies[6]} printed page 9",
    ]
    result = _create(
        client,
        _multipage_pdf(reference_pages),
        _multipage_pdf(comparison_pages),
    )

    comparison = result["report"]["comparisons"][0]
    page_seven_match = next(
        row for row in comparison["page_alignment"] if row["reference_page"] == 7
    )
    assert page_seven_match["comparison_page"] == 9
    assert page_seven_match["status"] == "changed"
    assert [
        row["reference_page"]
        for row in comparison["page_alignment"]
        if row["status"] == "reference_only"
    ] == [8, 9, 10]
    assert [
        row["comparison_page"]
        for row in comparison["page_alignment"]
        if row["status"] == "comparison_only"
    ] == [2, 3]
    assert {(change["kind"], change["page"]) for change in comparison["changes"]} == {
        ("removed", 7),
        ("added", 9),
    }
    assert all(
        "Inserted candidate page" not in change["text"]
        for change in comparison["changes"]
    )


def test_replaced_pages_below_similarity_threshold_remain_unmatched(
    client: TestClient,
) -> None:
    result = _create(
        client,
        _multipage_pdf(["Anchor start", "R" * 50, "Anchor end"]),
        _multipage_pdf(["Anchor start", "C" * 50, "Anchor end"]),
    )

    comparison = result["report"]["comparisons"][0]
    middle_pages = [
        row for row in comparison["page_alignment"]
        if row["reference_page"] == 2 or row["comparison_page"] == 2
    ]
    assert {row["status"] for row in middle_pages} == {
        "reference_only",
        "comparison_only",
    }
    assert comparison["changes"] == []


def test_page_similarity_threshold_changes_page_matching(client: TestClient) -> None:
    shared_text = "Rotor assembly"
    reference = _multipage_pdf([shared_text + " v1"])
    comparison = _multipage_pdf([shared_text + " v2"])

    permissive_result = _create(
        client,
        reference,
        comparison,
        page_similarity_threshold=50,
    )
    strict_result = _create(
        client,
        reference,
        comparison,
        page_similarity_threshold=99,
    )

    permissive_alignment = permissive_result["report"]["comparisons"][0]["page_alignment"]
    strict_alignment = strict_result["report"]["comparisons"][0]["page_alignment"]
    assert len(permissive_alignment) == 1
    assert permissive_alignment[0]["status"] == "changed"
    assert {row["status"] for row in strict_alignment} == {
        "reference_only",
        "comparison_only",
    }


def test_page_similarity_threshold_rejects_values_outside_supported_range(
    client: TestClient,
) -> None:
    reference = _multipage_pdf(["Reference page"])
    comparison = _multipage_pdf(["Comparison page"])
    for threshold in (49, 100):
        response = client.post(
            "/api/v1/comparisons",
            data={
                "reference_index": "0",
                "page_similarity_threshold": str(threshold),
            },
            files=[
                ("files", ("reference.pdf", reference, "application/pdf")),
                ("files", ("revision.pdf", comparison, "application/pdf")),
            ],
        )
        assert response.status_code == 422


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
    assert report["schema_version"] == 5
    assert comparison["changes"] == []
    assert comparison["added_count"] == 0
    assert comparison["removed_count"] == 0
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
        _multipage_pdf(["Reference procedure printed page 7"]),
        _multipage_pdf(["Reference procedure printed page 9"]),
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
        row.ai_summary_json = json.dumps(
            {"summary": "Stale", "key_changes": [], "impact": "Stale"}
        )
        row.ai_status = "completed"
        row.ai_summary_truncated = True
        db.commit()

    opened = client.get(f"/api/v1/comparisons/{result['id']}")
    assert opened.status_code == 200
    upgraded = opened.json()["report"]
    assert upgraded["schema_version"] == 5
    assert upgraded["page_slots"]
    assert upgraded["comparisons"][0]["page_alignment"]
    assert upgraded["comparisons"][0]["changes"][0]["group_id"]
    assert isinstance(upgraded["comparisons"][0]["changes"][0]["bbox"], dict)
    assert opened.json()["ai_summary"] is None
    assert opened.json()["ai_status"] == "pending"
    assert opened.json()["ai_summary_truncated"] is False
