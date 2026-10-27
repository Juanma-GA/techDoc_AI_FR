from __future__ import annotations

from types import SimpleNamespace

import fitz
import pytest
from fastapi.testclient import TestClient

from app.checks.thales_rules.preparation_detector import detect_pages_to_modify
from app.core.compiled_rules import RuleTarget
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def _upload(client: TestClient, pdf_bytes: bytes) -> str:
    response = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("synthetic.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _readable_pdf(headings: list[str | None]) -> bytes:
    pdf = fitz.open()
    for heading in headings:
        page = pdf.new_page(width=400, height=600)
        for line in range(6):
            page.insert_text(
                (40, 60 + line * 24),
                f"Readable native text on this page with enough detail for extraction {line}.",
                fontsize=10,
            )
        if heading:
            page.insert_text((40, 260), heading, fontsize=12)
        page.insert_text((40, 560), "Page 401", fontsize=9)
    data = pdf.tobytes()
    pdf.close()
    return data


def _classification_url(document_id: str, page: int) -> str:
    return f"/api/v1/documents/{document_id}/preparation/pages/{page}/classification"


def _page_type_options(client: TestClient, document_id: str) -> list[str]:
    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()
    return state["page_type_options"]


def test_state_exposes_page_types_targeted_by_preparation_rules(client: TestClient) -> None:
    document_id = _upload(client, _readable_pdf([None]))

    options = _page_type_options(client, document_id)

    assert options
    assert options == sorted(options)


def test_manual_classification_is_stored_validated_and_reverted(client: TestClient) -> None:
    document_id = _upload(client, _readable_pdf([None, None]))
    page_type = _page_type_options(client, document_id)[0]

    stored = client.patch(
        _classification_url(document_id, 2),
        json={"page_type": page_type, "document_page": "  ROR   12 "},
    )
    assert stored.status_code == 200, stored.text
    assert stored.json()["classification"] == {
        "page_type": page_type,
        "document_page": "ROR 12",
    }
    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()
    assert state["page_classification"] == {
        "2": {"page_type": page_type, "document_page": "ROR 12"}
    }

    reverted = client.patch(
        _classification_url(document_id, 2),
        json={"page_type": None, "document_page": None},
    )
    assert reverted.status_code == 200, reverted.text
    assert reverted.json()["classification"] is None
    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()
    assert state["page_classification"] == {}


@pytest.mark.parametrize(
    ("page", "body", "code"),
    [
        (1, {"page_type": "NOT_A_SECTION"}, "PAGE_TYPE_INVALID"),
        (1, {"document_page": "<script>"}, "DOCUMENT_PAGE_INVALID"),
        (1, {"document_page": "x" * 21}, "DOCUMENT_PAGE_INVALID"),
        (9, {"document_page": "1"}, "PAGE_RANGE_INVALID"),
    ],
)
def test_manual_classification_rejects_invalid_input(
    client: TestClient,
    page: int,
    body: dict,
    code: str,
) -> None:
    document_id = _upload(client, _readable_pdf([None]))

    response = client.patch(_classification_url(document_id, page), json=body)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == code
    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()
    assert state["page_classification"] == {}


def test_detection_reports_manual_and_automatic_sources(client: TestClient) -> None:
    document_id = _upload(client, _readable_pdf(["REPAIR", None]))
    page_type = next(
        item for item in _page_type_options(client, document_id) if item != "REPAIR"
    )
    client.patch(
        _classification_url(document_id, 2),
        json={"page_type": page_type, "document_page": "401"},
    )

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 200, response.text
    first, second = response.json()
    assert first["page_type"] == "REPAIR"
    assert first["page_type_source"] == "auto"
    assert first["detected_page_type"] == "REPAIR"
    assert first["document_page_source"] == "auto"
    assert second["page_type"] == page_type
    assert second["page_type_source"] == "manual"
    assert second["detected_page_type"] is None
    assert second["document_page"] == "401"
    assert second["document_page_source"] == "manual"
    assert "classification_evidence" in second


def test_reclassification_keeps_manual_decision_only_while_type_is_unchanged(
    client: TestClient,
) -> None:
    document_id = _upload(client, _readable_pdf([None]))
    first_type, second_type = _page_type_options(client, document_id)[:2]
    client.patch(_classification_url(document_id, 1), json={"page_type": first_type})
    assert client.post(f"/api/v1/documents/{document_id}/preparation/detect").status_code == 200
    decision = client.patch(
        f"/api/v1/documents/{document_id}/preparation/decisions/1",
        json={"is_modified": True},
    )
    assert decision.status_code == 200, decision.text

    same_type = client.patch(
        _classification_url(document_id, 1),
        json={"page_type": first_type, "document_page": "7"},
    )
    assert same_type.status_code == 200, same_type.text
    kept = same_type.json()["decisions"][0]
    assert kept["is_modified"] is True
    assert kept["manual_override"] is True
    assert kept["document_page"] == "7"

    changed_type = client.patch(
        _classification_url(document_id, 1),
        json={"page_type": second_type, "document_page": "7"},
    )
    assert changed_type.status_code == 200, changed_type.text
    recomputed = changed_type.json()["decisions"][0]
    assert recomputed["page_type"] == second_type
    assert "manual_override" not in recomputed


def test_mapping_change_invalidates_decisions_but_keeps_manual_classification(
    client: TestClient,
) -> None:
    document_id = _upload(client, _readable_pdf([None]))
    page_type = _page_type_options(client, document_id)[0]
    client.patch(_classification_url(document_id, 1), json={"page_type": page_type})
    assert client.post(f"/api/v1/documents/{document_id}/preparation/detect").status_code == 200
    assert client.get(f"/api/v1/documents/{document_id}/preparation").json()["page_decisions"]

    patched = client.patch(
        f"/api/v1/documents/{document_id}/preparation/mapping",
        json={"mapping": {"meta_cmm_number": "80-80-01"}},
    )
    assert patched.status_code == 200, patched.text

    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()
    assert state["page_decisions"] == []
    assert state["page_classification"] == {"1": {"page_type": page_type, "document_page": None}}


def test_ocr_rerun_and_readability_change_invalidate_decisions(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.core import preparation_ocr_service
    from app.core.ocr_types import OcrBox, OcrPageResult

    monkeypatch.setattr(
        preparation_ocr_service,
        "run_ocr",
        lambda provider, *_args: OcrPageResult(
            text="Synthetic OCR",
            boxes=[OcrBox(0.1, 0.1, 0.5, 0.2, "Synthetic OCR")],
            provider=provider,
            elapsed_ms=1,
        ),
    )
    document_id = _upload(client, _readable_pdf([None]))
    base = f"/api/v1/documents/{document_id}/preparation"

    def decisions() -> list:
        return client.get(base).json()["page_decisions"]

    assert client.post(f"{base}/detect").status_code == 200
    assert decisions()
    assert client.patch(f"{base}/pages/1", json={"needs_ocr": True}).status_code == 200
    assert decisions() == []

    assert client.post(f"{base}/ocr").status_code == 200
    assert client.post(f"{base}/ocr/validation").status_code == 200
    assert client.post(f"{base}/detect").status_code == 200
    assert decisions()
    rerun = client.post(f"{base}/ocr/pages/1", json={"provider": "mistral"})
    assert rerun.status_code == 200, rerun.text
    assert decisions() == []


def test_new_pdf_version_discards_manual_classification(client: TestClient) -> None:
    import uuid

    from app.core.pdf_versioning import bump_version
    from app.db.models import Document
    from app.db.session import SessionLocal

    document_id = _upload(client, _readable_pdf([None]))
    page_type = _page_type_options(client, document_id)[0]
    client.patch(_classification_url(document_id, 1), json={"page_type": page_type})

    with SessionLocal() as db:
        document = db.get(Document, uuid.UUID(document_id))
        bump_version(document.storage_dir, document.current_version)
        document.current_version += 1
        db.commit()

    state = client.get(f"/api/v1/documents/{document_id}/preparation").json()

    assert state["page_classification"] == {}


def test_ocr_text_and_boxes_feed_the_section_detection() -> None:
    from app.core.preparation_check_service import _apply_ocr_text
    from app.checks.thales_rules.section_detection import classify_preparation_sections
    from app.parsers.pdf_parser import parse_pdf

    pdf = fitz.open()
    pdf.new_page(width=400, height=600)
    parsed = parse_pdf(pdf.tobytes())
    pdf.close()
    _apply_ocr_text(
        parsed,
        [{"page": 1, "needs_ocr": True}],
        {
            "1": {
                "text": "REPAIR\nBody",
                "boxes": [
                    {"x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.15, "text": "REPAIR"},
                    {"x0": 0.1, "y0": 0.9, "x1": 0.4, "y1": 0.94, "text": "Page 650"},
                ],
            }
        },
    )

    analysis = classify_preparation_sections(parsed, {})

    assert parsed.pages[0].page_type == "REPAIR"
    assert analysis[1]["classification_status"] == "confirmed"


def test_detection_reports_section_status_and_uses_the_preparation_mapping(
    client: TestClient,
) -> None:
    pdf = fitz.open()
    for heading, footer in (("TESTING AND FAULT ISOLATION", "Page 150"), ("Plain", "")):
        page = pdf.new_page(width=400, height=600)
        for line in range(6):
            page.insert_text(
                (40, 60 + line * 24),
                f"Readable native text on this page with enough detail for extraction {line}.",
                fontsize=10,
            )
        page.insert_text((40, 260), heading, fontsize=12)
        if footer:
            page.insert_text((40, 560), footer, fontsize=9)
    data = pdf.tobytes()
    pdf.close()
    document_id = _upload(client, data)
    assert client.get(f"/api/v1/documents/{document_id}/preparation").status_code == 200

    response = client.post(f"/api/v1/documents/{document_id}/preparation/detect")

    assert response.status_code == 200, response.text
    first, second = response.json()
    assert first["page_type"] == "TESTING"
    assert first["classification_status"] == "confirmed"
    assert {item["family"] for item in first["classification_signals"]} == {"footer", "title"}
    assert second["classification_status"] == "unclassified"


def test_missing_required_page_types_are_requested_until_the_user_provides_them(
    client: TestClient,
) -> None:
    document_id = _upload(client, _readable_pdf([None, None]))
    base = f"/api/v1/documents/{document_id}/preparation"

    before_detection = client.get(base).json()
    assert before_detection["missing_page_types"] == []

    assert client.post(f"{base}/detect").status_code == 200
    missing = client.get(base).json()["missing_page_types"]
    assert ["TP1"] in missing
    assert ["TP2"] in missing

    provided = client.patch(
        _classification_url(document_id, 2),
        json={"page_type": "TP1", "document_page": "1"},
    )
    assert provided.status_code == 200, provided.text

    state = client.get(base).json()
    assert ["TP1"] not in state["missing_page_types"]
    assert ["TP2"] in state["missing_page_types"]
    assert state["page_decisions"][1]["page_type"] == "TP1"
    assert state["page_decisions"][1]["page_type_source"] == "manual"


def test_required_page_type_can_be_declared_absent_and_reports_skipped_rules(
    client: TestClient,
) -> None:
    document_id = _upload(client, _readable_pdf([None, None]))
    base = f"/api/v1/documents/{document_id}/preparation"
    absent_url = f"{base}/absent-page-types"
    assert client.post(f"{base}/detect").status_code == 200
    assert client.get(base).json()["skipped_rules"] == []

    invalid = client.patch(absent_url, json={"page_types": ["NOT_A_SECTION"], "absent": True})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "PAGE_TYPE_INVALID"

    declared = client.patch(absent_url, json={"page_types": ["TP1"], "absent": True})
    assert declared.status_code == 200, declared.text
    state = client.get(base).json()
    assert ["TP1"] not in state["missing_page_types"]
    assert ["TP1"] in state["absent_page_types"]
    assert state["skipped_rules"]
    assert all(item["page_types"] == ["TP1"] for item in state["skipped_rules"])
    assert {"rule_id", "title"} <= set(state["skipped_rules"][0])

    undone = client.patch(absent_url, json={"page_types": ["TP1"], "absent": False})
    assert undone.status_code == 200, undone.text
    state = client.get(base).json()
    assert ["TP1"] in state["missing_page_types"]
    assert state["absent_page_types"] == []
    assert state["skipped_rules"] == []


def test_providing_a_page_clears_its_absent_declaration(client: TestClient) -> None:
    document_id = _upload(client, _readable_pdf([None]))
    base = f"/api/v1/documents/{document_id}/preparation"
    assert client.post(f"{base}/detect").status_code == 200
    client.patch(f"{base}/absent-page-types", json={"page_types": ["TP1"], "absent": True})

    provided = client.patch(_classification_url(document_id, 1), json={"page_type": "TP1"})

    assert provided.status_code == 200, provided.text
    state = client.get(base).json()
    assert state["absent_page_types"] == []
    assert state["skipped_rules"] == []


def _bundle(classifier=None) -> SimpleNamespace:
    return SimpleNamespace(
        page_classifier=classifier,
        operations={},
        mapping=SimpleNamespace(entities={}),
    )


def test_detector_manual_type_selects_rules_and_keeps_detected_type(monkeypatch) -> None:
    rule = SimpleNamespace(
        id="TP2-CHECK",
        topic="TP2 check",
        target=RuleTarget(page="all", region="full_page", page_type="TP2"),
        failure_message=None,
        source_instruction=None,
        checks=[],
    )
    seen_pages: list[int] = []

    def fake_execute(scoped, *_args, **_kwargs):
        seen_pages.append(scoped.pages[0].page)
        return [SimpleNamespace(rule_id="TP2-CHECK", status="PASS")], []

    monkeypatch.setattr(
        "app.checks.thales_rules.preparation_detector.execute_pdf_rules", fake_execute
    )
    monkeypatch.setattr(
        "app.checks.thales_rules.preparation_detector.map_preparation_pages_to_toc",
        lambda *_args, **_kwargs: None,
    )

    def classifier(parsed, _document) -> None:
        parsed.pages[0].page_type = "TP1"

    parsed = ParsedPdf(
        page_count=2,
        pages=[ParsedPage(page=1, text="a"), ParsedPage(page=2, text="b")],
        full_text="a b",
        is_signed=False,
    )

    decisions = detect_pages_to_modify(
        parsed,
        SimpleNamespace(),
        [rule],
        None,
        _bundle(classifier),
        {"1": {"page_type": "TP2", "document_page": "12"}},
    )

    assert seen_pages == [1]
    assert decisions[0]["page_type"] == "TP2"
    assert decisions[0]["detected_page_type"] == "TP1"
    assert decisions[0]["page_type_source"] == "manual"
    assert decisions[0]["document_page"] == "12"
    assert decisions[1]["page_type"] is None
    assert decisions[1]["page_type_source"] == "unclassified"
    assert decisions[1]["decision_status"] == "no_applicable_rule"


def test_detector_document_page_only_override_keeps_detected_type(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.checks.thales_rules.preparation_detector.map_preparation_pages_to_toc",
        lambda *_args, **_kwargs: None,
    )

    def classifier(parsed, _document) -> None:
        parsed.pages[0].page_type = "TP1"

    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="a")],
        full_text="a",
        is_signed=False,
    )

    decisions = detect_pages_to_modify(
        parsed,
        SimpleNamespace(),
        [],
        None,
        _bundle(classifier),
        {"1": {"page_type": None, "document_page": "5"}},
    )

    assert decisions[0]["page_type"] == "TP1"
    assert decisions[0]["page_type_source"] == "auto"
    assert decisions[0]["document_page"] == "5"
    assert decisions[0]["document_page_source"] == "manual"
