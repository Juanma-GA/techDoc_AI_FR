"""POST /documents/{id}/analyze — SSE smoke test.

We don't parse the full SSE stream tightly; we just verify the endpoint
returns text/event-stream content and that suggestions are persisted.
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from fastapi.testclient import TestClient

from app.api import rules as rules_api
from app.core.compiled_rules import Check, CompiledRule, RuleTarget


def test_analyze_emits_events_and_persists(client: TestClient, sample_pdf_bytes: bytes) -> None:
    upload = client.post(
        "/api/v1/documents?target=imperial",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze") as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        body = b"".join(stream.iter_bytes())

    assert b"run_started" in body
    assert b"done" in body

    sugs = client.get(f"/api/v1/documents/{doc_id}/suggestions")
    assert sugs.status_code == 200
    rows = sugs.json()
    # At least one units suggestion should pop up because the fixture pdf
    # contains both "12 cm" and "5 in".
    assert any(r["rule_kind"] == "units" for r in rows)


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

    def compile_rule(_db, row, filename: str) -> CompiledRule:
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

    with client.stream("POST", f"/api/v1/documents/{doc_id}/analyze?checklist=true") as stream:
        assert stream.status_code == 200
        body = b"".join(stream.iter_bytes())
    assert b"done" in body

    suggestions = client.get(f"/api/v1/documents/{doc_id}/suggestions").json()
    assert any(
        row["rule_code"] == "compiled-2" and row["original_text"] == "12 cm"
        for row in suggestions
    )
