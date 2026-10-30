"""Validation de Data Modules importes sans BREX."""

from __future__ import annotations

import asyncio
import inspect
import threading

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import brex, extract, resources, validation
from app.core.dm_validation import validate_dm
from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.s1000d_serializer import serialize
from app.core.validator import xsd_is_valid


def _valid_dm(issue: str = "4.1", dm_type: str = "descriptive") -> str:
    paragraph = IRNode(id="paragraph", kind="paragraph", text="Contenu.")
    section = IRNode(id="section", kind="section", level=1, text="1 Test", children=[paragraph])
    if dm_type == "procedural":
        section.context = "procedural"
        paragraph.context = "procedural"
    root = IRNode(id="root", kind="section", level=0, children=[
        section,
    ])
    resolve(root)
    info_code = "520" if dm_type == "procedural" else "040"
    return serialize(
        root,
        issue=issue,
        dm_type=dm_type,
        dm_metadata={"dmc": f"DMC-WEG-A-00-00-00-00A-{info_code}A-D"},
    )


def test_xsd_gate_rejects_errors_and_unverifiable_issues_but_ignores_brex() -> None:
    assert xsd_is_valid([])
    assert not xsd_is_valid([{"rule": "XSD", "severity": "info"}])
    assert not xsd_is_valid([{"rule": "XSD", "severity": "error"}])
    assert not xsd_is_valid([{"rule": "WELLFORMED", "severity": "error"}])
    assert xsd_is_valid([{"rule": "BREX", "severity": "error"}])


def test_detects_issue_and_schema_from_schema_location() -> None:
    result = validate_dm(_valid_dm("4.1").encode(), filename="test.xml")

    assert result["status"] == "valid"
    assert result["issue"] == "4.1"
    assert result["schema"] == "descript"
    assert result["error_count"] == 0


def test_detects_issue_42_procedural_schema() -> None:
    result = validate_dm(
        _valid_dm("4.2", "procedural").encode(),
        filename="procedural.xml",
    )

    assert result["status"] == "valid"
    assert result["issue"] == "4.2"
    assert result["schema"] == "proced"


def test_reports_xsd_location_for_invalid_element() -> None:
    xml = _valid_dm().replace("</content>", "<notAS1000DElement/></content>")

    result = validate_dm(xml.encode(), filename="invalid.xml")

    assert result["status"] == "invalid"
    error = next(v for v in result["violations"] if v["rule"] == "XSD")
    assert error["line"] > 0
    assert error["path"]
    assert error["message"]


def test_unknown_issue_waits_for_user_selection() -> None:
    xml = _valid_dm().replace(
        'xsi:noNamespaceSchemaLocation="http://www.s1000d.org/S1000D_4-1/xml_schema_flat/descript.xsd"',
        "",
    )

    result = validate_dm(xml.encode(), filename="unknown.xml")

    assert result["status"] == "needs_issue"
    assert result["issue"] is None


def test_issue_five_is_reported_as_unverifiable_without_schema() -> None:
    result = validate_dm(_valid_dm().encode(), filename="legacy.xml", issue_override="5.0")

    assert result["status"] == "unverifiable"
    assert result["issue"] == "5.0"
    assert result["error_count"] == 0


def test_validation_api_accepts_multiple_dms(client) -> None:
    valid = _valid_dm("4.1").encode()
    invalid = _valid_dm("4.2").replace("</content>", "<notAS1000DElement/></content>").encode()

    response = client.post(
        "/api/v1/validation/dms",
        files=[
            ("files", ("valid.xml", valid, "application/xml")),
            ("files", ("invalid.xml", invalid, "application/xml")),
        ],
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert [result["status"] for result in results] == ["valid", "invalid"]
    assert [result["issue"] for result in results] == ["4.1", "4.2"]


@pytest.mark.parametrize("endpoint", [
    validation.validate_dms,
    extract.upload_document,
    resources.upload_resource,
    brex.upload_brex,
])
def test_blocking_handlers_are_synchronous(endpoint) -> None:
    assert not inspect.iscoroutinefunction(endpoint)


async def test_validation_batch_keeps_event_loop_responsive(app, monkeypatch, pdf_bytes) -> None:
    from app.api import validation as validation_api

    xml = _valid_dm().encode()
    loop_thread = threading.get_ident()
    started = threading.Event()
    release = threading.Event()

    def blocking_validate(data: bytes, *, filename: str, issue_override: str | None = None) -> dict:
        started.set()
        assert threading.get_ident() != loop_thread
        if not release.wait(timeout=10):
            raise TimeoutError("Validation worker was not released.")
        return validate_dm(data, filename=filename, issue_override=issue_override)

    monkeypatch.setattr(validation_api, "validate_dm", blocking_validate)

    def extraction_progress(doc_id, progress_cb, _demo_mode):
        progress_cb("parse", 10)
        progress_cb("infer", 50)
        progress_cb("done", 100)
        return {"document_id": doc_id}

    monkeypatch.setattr(extract, "_run_and_persist", extraction_progress)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        validation_task = asyncio.create_task(client.post(
            "/api/v1/validation/dms",
            files=[
                ("files", (f"DM-{index}.xml", xml, "application/xml"))
                for index in range(50)
            ],
        ))
        try:
            assert await asyncio.to_thread(started.wait, 5)
            health = await asyncio.wait_for(client.get("/api/v1/health"), timeout=5)
            assert health.status_code == 200
            uploaded = await asyncio.wait_for(client.post(
                "/api/v1/documents", files={"file": ("synthetic.pdf", pdf_bytes)},
            ), timeout=5)
            assert uploaded.status_code == 201
            doc_id = uploaded.json()["id"]
            stream = await asyncio.wait_for(
                client.post(f"/api/v1/documents/{doc_id}/extract"), timeout=5,
            )
            assert stream.status_code == 200
            assert "event: progress" in stream.text
            assert '"pct": 50' in stream.text
            assert "event: done" in stream.text
            assert not validation_task.done()
        finally:
            release.set()
            response = await asyncio.wait_for(validation_task, timeout=30)

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 50
    assert all(result["status"] == "valid" for result in results)


def test_validates_declared_legacy_encoding() -> None:
    xml = _valid_dm().replace("encoding='UTF-8'", "encoding='ISO-8859-1'").replace(
        "Contenu.", "Résumé."
    )

    result = validate_dm(xml.encode("iso-8859-1"), filename="legacy-encoding.xml")

    assert result["status"] == "valid"