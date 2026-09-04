"""POST /documents/{id}/analyze — SSE smoke test.

We don't parse the full SSE stream tightly; we just verify the endpoint
returns text/event-stream content and that suggestions are persisted.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


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
