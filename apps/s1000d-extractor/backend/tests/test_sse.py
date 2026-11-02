"""Shared threaded SSE jobs preserve events and cancel cooperatively."""

import asyncio
import json
from threading import Event
from types import SimpleNamespace

import pytest

from app.core.sse import JobCancelled, stream_threaded_job


@pytest.mark.parametrize("route", ["extract", "wizard/start_stream", "validate-and-generate-pmc"])
def test_routes_emit_session_progress_and_done(client, pdf_bytes_image, route) -> None:
    uploaded = client.post("/api/v1/documents", files={"file": ("source.pdf", pdf_bytes_image)})
    doc_id = uploaded.json()["id"]
    if route == "validate-and-generate-pmc":
        dmrl = [{"DMC": "DMC-PUMP-A-00-00-00-00A-040A-D", "Titre": "Description"}]
        assert (
            client.post(
                f"/api/v1/documents/{doc_id}/resources/dmrl",
                files={"file": ("dmrl.json", json.dumps(dmrl).encode())},
            ).status_code
            == 200
        )
    response = client.post(f"/api/v1/documents/{doc_id}/{route}", json={"cut_pdf": False})
    assert response.status_code == 200, response.text
    events = [
        line.removeprefix("event: ").strip()
        for line in response.text.splitlines()
        if line.startswith("event:")
    ]
    assert events[0] == "session"
    assert "progress" in events
    assert events[-1] == "done"
    assert "error" not in events


@pytest.mark.parametrize("route", ["extract", "wizard/start_stream", "validate-and-generate-pmc"])
def test_routes_emit_session_and_error_on_job_failure(client, route) -> None:
    uploaded = client.post("/api/v1/documents", files={"file": ("source.pdf", b"invalid synthetic PDF")})
    doc_id = uploaded.json()["id"]
    response = client.post(f"/api/v1/documents/{doc_id}/{route}", json={"cut_pdf": False})
    assert response.status_code == 200
    events = [line for line in response.text.splitlines() if line.startswith("event:")]
    assert events[0] == "event: session"
    assert events[-1] == "event: error"
    assert "event: done" not in events


async def test_disconnect_signals_running_worker_and_stops_events() -> None:
    started = Event()
    stopped = Event()

    def work(progress):
        started.set()
        try:
            while not progress.cancelled.wait(0.01):
                progress.check_cancelled()
            progress.check_cancelled()
        except JobCancelled:
            stopped.set()
            raise

    async def disconnected():
        assert await asyncio.to_thread(started.wait, 5)
        return True

    response = stream_threaded_job(
        SimpleNamespace(is_disconnected=disconnected),
        work,
        session_data={"document_id": "synthetic"},
        error_code="TEST_FAILED",
    )
    events = [event async for event in response.body_iterator]
    assert [event["event"] for event in events] == ["session"]
    assert await asyncio.to_thread(stopped.wait, 5)


def test_cancelled_extraction_does_not_commit_a_failure_status(client, pdf_bytes_image, monkeypatch) -> None:
    from app.api import extract
    from app.db.models import Document
    from app.db.session import SessionLocal

    uploaded = client.post("/api/v1/documents", files={"file": ("source.pdf", pdf_bytes_image)})
    doc_id = uploaded.json()["id"]

    def cancelled(*_args, **_kwargs):
        raise JobCancelled()

    monkeypatch.setattr(extract.pipeline, "run", cancelled)
    with pytest.raises(JobCancelled):
        extract._run_and_persist(doc_id, lambda *_args: None)
    with SessionLocal() as db:
        assert db.get(Document, doc_id).status == "uploaded"
