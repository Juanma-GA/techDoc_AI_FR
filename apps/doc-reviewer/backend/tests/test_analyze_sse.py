"""POST /documents/{id}/analyze — SSE smoke test.

We don't parse the full SSE stream tightly; we just verify the endpoint
returns text/event-stream content and that suggestions are persisted.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select

from app.api import analyze as analyze_api
from app.api import rules as rules_api
from app.api.analyze import latest_rule_results
from app.checks.client_registry import load_active_client_configuration
from app.core.compiled_rules import Check, CompiledRule, RuleTarget
from app.db.models import AnalysisRun, Document
from app.db.session import SessionLocal


def test_rule_results_include_human_readable_titles_from_synthetic_snapshot() -> None:
    from app.db.models import Document

    snapshot = {
        "rules": [{"id": "CHECKLIST_REVISION_DATE", "topic": "Revision date"}],
        "results": [
            {
                "rule_id": "CHECKLIST_REVISION_DATE",
                "inconclusive_pages": ["24", "26"],
                "status": "INCONCLUSIVE",
                "evidence": {
                    "page": "1",
                    "location": {"type": "bbox", "bbox": [0, 0, 0, 0]},
                    "observed_value": None,
                    "expected_value": None,
                },
            }
        ],
    }
    document_id = uuid.uuid4()
    run = SimpleNamespace(compiled_rules_snapshot_json=json.dumps(snapshot))
    document = SimpleNamespace(id=document_id)

    class FakeDb:
        def get(self, _model, _key):
            return None

        def scalar(self, statement):
            if statement.column_descriptions[0]["entity"] is Document:
                return document
            return run

    results = latest_rule_results(document_id, FakeDb())  # type: ignore[arg-type]

    assert len(results) == 1
    assert results[0].status == "INCONCLUSIVE"
    assert results[0].rule_title == "Revision date"
    assert results[0].inconclusive_pages == ["24", "26"]


def _set_document_context(client: TestClient, document_id: str) -> None:
    response = client.patch(
        f"/api/v1/documents/{document_id}",
        json={
            "meta_revision_date": "JUL 27/26",
            "meta_cmm_number": "79-30-02",
            "meta_first_issue_date": "JUL 1966",
            "meta_revision_number": "Rev. 01",
            "document_language": "en",
        },
    )
    assert response.status_code == 200, response.text


def test_analyze_requires_complete_document_context(client: TestClient, sample_pdf_bytes: bytes) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    blocked = client.post(f"/api/v1/documents/{doc_id}/analyze")

    assert blocked.status_code == 409
    assert blocked.json()["code"] == "DOCUMENT_CONTEXT_INCOMPLETE"
    assert set(blocked.json()["detail"]["fields"]) == {
        "meta_revision_date",
        "meta_cmm_number",
        "meta_first_issue_date",
        "meta_revision_number",
        "document_language",
    }


def test_analyze_emits_events_and_persists(client: TestClient, sample_pdf_bytes: bytes) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]
    _set_document_context(client, doc_id)

    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze") as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        body = b"".join(stream.iter_bytes())

    assert b"run_started" in body
    assert b"done" in body
    assert b"event: page_statuses" in body
    assert b'"unit": "page"' in body
    assert b'"step": "suggestions"' in body
    parse_complete = body.find(b'"step": "parse", "pct": 95')
    rules_started = body.find(b'"step": "rules", "pct": 95')
    rules_complete = body.find(b'"step": "finalize", "pct": 97')
    suggestions_complete = body.find(b'"step": "suggestions", "pct": 99')
    done = body.find(b"event: done")
    assert 0 <= parse_complete < rules_started < rules_complete < suggestions_complete < done

    sugs = client.get(f"/api/v1/documents/{doc_id}/suggestions")
    assert sugs.status_code == 200
    rows = sugs.json()
    # At least one units suggestion should pop up because the fixture pdf
    # contains both "12 cm" and "5 in".
    assert any(r["rule_kind"] == "units" for r in rows)


def test_undecided_revision_pages_are_reviewed_before_analysis(
    client: TestClient,
    monkeypatch,
) -> None:
    import fitz

    pdf = fitz.open()
    for page_number in range(1, 3):
        page = pdf.new_page(width=400, height=300)
        text = "HIGHLIGHTS" if page_number == 1 else f"Synthetic page content {page_number}."
        page.insert_text((40, 100), text)
    pdf_bytes = pdf.tobytes()
    pdf.close()

    standards = client.get("/api/v1/standards")
    custom = next(item for item in standards.json() if item["code"] == "THALES-CUSTOM")
    version_id = custom["versions"][0]["id"]
    upload = client.post(
        f"/api/v1/documents?target=imperial&standard_version_ids={version_id}",
        files={"file": ("synthetic.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    _set_document_context(client, document_id)

    analyzed_pages: list[int] = []

    def capture_rule_pages(parsed, *_args, **_kwargs):
        analyzed_pages.extend(page.page for page in parsed.pages)
        return []

    monkeypatch.setattr(analyze_api, "run_all", capture_rule_pages)

    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze") as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes()).decode("utf-8").replace("\r\n", "\n")

    page_status_event = next(
        block for block in body.split("\n\n") if block.startswith("event: page_statuses")
    )
    status_payload = json.loads(
        next(line[5:].strip() for line in page_status_event.splitlines() if line.startswith("data:"))
    )
    assert status_payload["pages"] == [
        {
            "page": 1,
            "is_modified": True,
            "source": "detected",
            "requires_review": False,
        },
        {
            "page": 2,
            "is_modified": None,
            "source": "detected",
            "requires_review": True,
        },
    ]
    assert analyzed_pages == [1]


def test_analyze_accepts_previous_revision_pdf(
    client: TestClient,
    sample_pdf_bytes: bytes,
    monkeypatch,
) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    _set_document_context(client, document_id)

    captured_previous: list = []

    def capture_previous(*_args, **kwargs):
        captured_previous.append(kwargs["previous_revision_pdf"])
        return []

    monkeypatch.setattr(analyze_api, "run_all", capture_previous)

    with client.stream(
        "POST",
        f"/api/v1/documents/{document_id}/analyze",
        files={
            "previous_revision_file": (
                "manual-rev-00.pdf",
                sample_pdf_bytes,
                "application/pdf",
            )
        },
    ) as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())

    assert b"done" in body
    assert len(captured_previous) == 1
    assert captured_previous[0].page_count == 1


def test_analyze_rejects_non_pdf_previous_revision(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    _set_document_context(client, document_id)

    response = client.post(
        f"/api/v1/documents/{document_id}/analyze",
        files={
            "previous_revision_file": (
                "manual-rev-00.docx",
                sample_pdf_bytes,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PREVIOUS_REVISION_BAD_FORMAT"


def test_analyze_rejects_invalid_pdf_previous_revision(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    _set_document_context(client, document_id)

    response = client.post(
        f"/api/v1/documents/{document_id}/analyze",
        files={
            "previous_revision_file": (
                "manual-rev-00.pdf",
                b"not a PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PREVIOUS_REVISION_INVALID_PDF"


def test_manual_page_rerun_preserves_suggestions_on_other_pages(
    client: TestClient,
) -> None:
    import fitz

    pdf = fitz.open()
    for page_number in range(1, 3):
        page = pdf.new_page(width=400, height=300)
        page.insert_text(
            (40, 100),
            f"Replace the fitting after 12 cm on page {page_number}.",
            fontname="helv",
            fontsize=12,
        )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("two-pages.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    _set_document_context(client, document_id)

    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze") as stream:
        assert stream.status_code == 200
        first_body = b"".join(stream.iter_bytes())
    assert b"done" in first_body

    before = client.get(f"/api/v1/documents/{document_id}/suggestions").json()
    page_two_ids = {item["id"] for item in before if item["page"] == 2}
    assert page_two_ids

    with client.stream(
        "POST",
        f"/api/v1/documents/{document_id}/analyze",
        params={
            "modified_only": "false",
            "page_number": "1",
            "page_overrides": json.dumps({"1": True}),
        },
    ) as stream:
        assert stream.status_code == 200
        rerun_body = b"".join(stream.iter_bytes())

    assert b"event: page_statuses" in rerun_body
    assert b'"is_modified": true' in rerun_body
    after = client.get(f"/api/v1/documents/{document_id}/suggestions").json()
    assert page_two_ids <= {item["id"] for item in after}

    with SessionLocal() as session:
        run_ids_before_delete = session.scalars(
            select(AnalysisRun.id).where(
                AnalysisRun.document_id == uuid.UUID(document_id)
            )
        ).all()

    cleared = client.delete(
        f"/api/v1/documents/{document_id}/pages/1/suggestions"
    )
    assert cleared.status_code == 204, cleared.text

    unchanged = client.get(f"/api/v1/documents/{document_id}/suggestions").json()
    assert not any(item["page"] == 1 and item["status"] not in {"applied", "rejected"} for item in unchanged)
    assert page_two_ids <= {item["id"] for item in unchanged}
    with SessionLocal() as session:
        run_ids_after_delete = session.scalars(
            select(AnalysisRun.id).where(
                AnalysisRun.document_id == uuid.UUID(document_id)
            )
        ).all()
    assert run_ids_after_delete == run_ids_before_delete


def test_unchanged_page_is_removed_before_rules_run(
    client: TestClient,
    monkeypatch,
) -> None:
    import fitz

    pdf = fitz.open()
    for page_number in range(1, 3):
        page = pdf.new_page(width=400, height=300)
        page.insert_text(
            (40, 100),
            f"Replace the fitting after 12 cm on page {page_number}.",
            fontname="helv",
            fontsize=12,
        )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("two-pages.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    _set_document_context(client, document_id)

    analyzed_pages: list[int] = []

    def capture_rule_pages(parsed, *_args, **_kwargs):
        analyzed_pages.extend(page.page for page in parsed.pages)
        return []

    monkeypatch.setattr(analyze_api, "run_all", capture_rule_pages)

    with client.stream(
        "POST",
        f"/api/v1/documents/{document_id}/analyze",
        params={
            "modified_only": "false",
            "page_overrides": json.dumps({"1": False}),
        },
    ) as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())

    assert b"done" in body
    assert analyzed_pages == [2]


def test_page_review_rerun_adds_manually_modified_pages_outside_original_range(
    client: TestClient,
    monkeypatch,
) -> None:
    import fitz

    pdf = fitz.open()
    for page_number in range(1, 4):
        page = pdf.new_page(width=400, height=300)
        page.insert_text((40, 100), f"Manual text on page {page_number}.")
    pdf_bytes = pdf.tobytes()
    pdf.close()

    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("three-pages.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    _set_document_context(client, document_id)

    analyzed_pages: list[int] = []

    def capture_rule_pages(parsed, *_args, **_kwargs):
        analyzed_pages.extend(page.page for page in parsed.pages)
        return []

    monkeypatch.setattr(analyze_api, "run_all", capture_rule_pages)

    with client.stream(
        "POST",
        f"/api/v1/documents/{document_id}/analyze",
        params=[
            ("first_page", "2"),
            ("last_page", "3"),
            ("additional_pages", "1"),
            ("page_overrides", json.dumps({"1": True, "2": True, "3": False})),
        ],
    ) as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())

    assert b"done" in body
    assert analyzed_pages == [1, 2]


def test_analyze_stores_tp1_page_type_in_context_snapshot(client: TestClient) -> None:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page(width=400, height=300)
    page.insert_text((40, 100), "Title page body", fontname="helv", fontsize=12)
    page.insert_text((40, 240), "Revision: JUL 27/26", fontname="helv", fontsize=8)
    page.insert_text((40, 252), "TP 1", fontname="helv", fontsize=8)
    pdf_bytes = pdf.tobytes()
    pdf.close()

    # La classification TP1 est portée par le bundle THALES actif.
    standards = client.get("/api/v1/standards")
    custom = next(item for item in standards.json() if item["code"] == "THALES-CUSTOM")
    version_id = custom["versions"][0]["id"]

    upload = client.post(
        f"/api/v1/documents?target=imperial&standard_version_ids={version_id}",
        files={"file": ("tp1.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]
    client_configuration = load_active_client_configuration()
    expected_version_ids = [
        catalog["standard_version_id"]
        for catalog in client.get("/api/v1/client-config").json()["catalogs"]
    ]
    with SessionLocal() as session:
        historical_document = session.get(Document, uuid.UUID(doc_id))
        assert historical_document is not None
        historical_document.standard_version_id = None
        historical_document.standard_version_ids = "[]"
        session.commit()
    _set_document_context(client, doc_id)

    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze") as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())
    assert b"done" in body

    with SessionLocal() as session:
        run = session.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.document_id == uuid.UUID(doc_id))
            .order_by(AnalysisRun.started_at.desc())
            .limit(1)
        )
        assert run is not None
        snapshot = json.loads(run.context_snapshot_json)
        bundle_snapshot = snapshot["client_bundle"]
        assert bundle_snapshot["bundle"] == client_configuration.selection.bundle
        assert bundle_snapshot["client_code"] == client_configuration.manifest.client_code
        assert bundle_snapshot["bundle_version"] == client_configuration.manifest.bundle_version
        assert bundle_snapshot["contract_version"] == client_configuration.manifest.contract_version
        assert bundle_snapshot["catalogs"] == [
            catalog.model_dump(mode="json")
            for catalog in client_configuration.bundle.catalogs
        ]
        assert bundle_snapshot["manifest_hash"] == client_configuration.manifest_hash
        assert bundle_snapshot["mapping_hash"] == client_configuration.mapping_hash
        assert bundle_snapshot["bundle_hash"] == client_configuration.bundle_hash
        assert snapshot["metadata"]["client_metadata"]["meta_cmm_number"] == "79-30-02"
        assert run.standard_version_id == uuid.UUID(version_id)
        assert json.loads(run.standard_version_ids) == expected_version_ids
        assert run.snapshot_sha256 == hashlib.sha256(
            f"{run.context_snapshot_json}\n{run.compiled_rules_snapshot_json}".encode("utf-8")
        ).hexdigest()
        historical_document = session.get(Document, uuid.UUID(doc_id))
        assert historical_document is not None
        assert historical_document.standard_version_id is None
        assert json.loads(historical_document.standard_version_ids) == []

    assert snapshot["page_types"] == {"1": "TP1"}


def test_reanalysis_warns_when_previous_bundle_is_unavailable(
    client: TestClient,
    sample_pdf_bytes: bytes,
) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    _set_document_context(client, document_id)

    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze") as stream:
        assert stream.status_code == 200
        first_body = b"".join(stream.iter_bytes())
    assert b"done" in first_body

    with SessionLocal() as session:
        previous_run = session.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.document_id == uuid.UUID(document_id))
            .order_by(AnalysisRun.started_at.desc())
            .limit(1)
        )
        assert previous_run is not None
        previous_snapshot = json.loads(previous_run.context_snapshot_json)
        previous_snapshot["client_bundle"]["bundle_hash"] = "unavailable-previous-bundle"
        previous_run.context_snapshot_json = json.dumps(previous_snapshot)
        session.commit()

    with client.stream("POST", f"/api/v1/documents/{document_id}/analyze") as stream:
        assert stream.status_code == 200
        second_body = b"".join(stream.iter_bytes())
    assert b"bundle actif" in second_body

    with SessionLocal() as session:
        current_run = session.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.document_id == uuid.UUID(document_id))
            .order_by(AnalysisRun.started_at.desc())
            .limit(1)
        )
        assert current_run is not None
        reanalysis = json.loads(current_run.context_snapshot_json)["client_bundle"]["reanalysis"]
        assert reanalysis == {
            "previous_bundle_hash": "unavailable-previous-bundle",
            "using_current_bundle": True,
        }


def test_imported_compiled_rule_comments_matching_pdf_text(
    client: TestClient,
    sample_pdf_bytes: bytes,
    monkeypatch,
) -> None:
    workbook = Workbook()
    workbook.active.append(["Topic", "Check"])
    workbook.active.append(["Torque", "The document must not contain 12 cm."])
    checklist = io.BytesIO()
    workbook.save(checklist)

    def compile_rule(_db, row, filename: str, *, client_bundle=None) -> CompiledRule:
        return CompiledRule(
            id=f"compiled-{row.row_number}",
            topic=row.category,
            execution="deterministic",
            target=RuleTarget(page="all", region="full_page"),
            checks=[Check(field="text", operator="regex", expected=r"12 cm")],
            source="user_checklist",
            origin_ref=f"{filename}:{row.sheet}:{row.row_number}",
        )

    monkeypatch.setattr(rules_api, "compile_checklist_rule", compile_rule)
    imported = client.post(
        "/api/v1/rules/import",
        files={"file": ("checklist.xlsx", checklist.getvalue(), "application/vnd.ms-excel")},
        data={"mode": "replace"},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["rules"][0]["active"] is True

    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]
    _set_document_context(client, doc_id)

    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze?checklist=true") as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())
    assert b"done" in body

    suggestions = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    assert any(
        row["rule_code"] == "compiled-2" and row["original_text"] == "12 cm"
        for row in suggestions
    )
