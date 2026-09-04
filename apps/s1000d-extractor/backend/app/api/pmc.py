"""Streaming PMC validation and generation routes."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.core import dmrl as dmrl_mod
from app.core.errors import AppError
from app.core.pmc import generate_pmc
from app.db.models import Document
from app.db.session import SessionLocal, get_db

router = APIRouter(prefix="/documents", tags=["pmc"])


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


@router.post("/{doc_id}/validate-and-generate-pmc")
async def validate_and_generate_pmc(
    doc_id: str, db: Session = Depends(get_db)
) -> EventSourceResponse:
    """Validate the persisted DMRL and stream PMC generation progress."""
    _require(db, doc_id)

    async def gen():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def step(name: str, current: int, total: int) -> None:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("validation_step", {"step": name, "current": current, "total": total}),
            )

        def work() -> dict:
            session = SessionLocal()
            try:
                document = session.get(Document, doc_id)
                if document is None:
                    raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
                if not document.dmrl_json:
                    raise AppError("NO_DMRL", "Aucune DMRL attachée au document.", 409)

                raw_entries = json.loads(document.dmrl_json)
                if not isinstance(raw_entries, list):
                    raise AppError("DMRL_PARSE_ERROR", "La DMRL doit être une liste.", 422)
                total = len(raw_entries)
                entries = []
                for index, raw_entry in enumerate(raw_entries, start=1):
                    if not isinstance(raw_entry, dict):
                        raise AppError("DMRL_PARSE_ERROR", f"Ligne DMRL invalide : {index}.", 422)
                    entry = dmrl_mod.entry_from_dict(raw_entry)
                    if not entry.dmc:
                        raise AppError("DMRL_MISSING_DMC", f"DMC manquant à la ligne {index}.", 422)
                    entries.append(entry)
                    step("validated", index, total)

                xml = generate_pmc(entries, pm_title=document.filename)
                return {"document_id": doc_id, "entries": total, "pmc": xml}
            finally:
                session.close()

        task = asyncio.create_task(asyncio.to_thread(work))
        yield {"event": "validation_started", "data": json.dumps({"document_id": doc_id})}
        while True:
            getter = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait({getter, task}, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                event, data = getter.result()
                yield {"event": event, "data": json.dumps(data)}
            else:
                getter.cancel()
            if task.done() and queue.empty():
                break

        try:
            result = task.result()
            yield {
                "event": "pmc_generated",
                "data": json.dumps({"document_id": doc_id, "entries": result["entries"]}),
            }
            yield {"event": "done", "data": json.dumps(result)}
        except Exception as exc:
            code = exc.code if isinstance(exc, AppError) else "PMC_GENERATION_FAILED"
            yield {"event": "error", "data": json.dumps({"code": code, "message": str(exc)})}

    return EventSourceResponse(gen())
