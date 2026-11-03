"""Streaming PMC validation and generation routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core import dmrl as dmrl_mod
from app.core.demo_mode import is_demo_mode
from app.core.dmrl_rules import is_pm_title
from app.core.errors import AppError
from app.core.pmc import generate_pmc
from app.core.sse import Progress, stream_threaded_job
from app.db.models import Document
from app.db.session import get_db, open_session

router = APIRouter(prefix="/documents", tags=["pmc"])


def _require(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError("DOC_NOT_FOUND", "Document inconnu.", 404)
    return doc


@router.post("/{doc_id}/validate-and-generate-pmc")
async def validate_and_generate_pmc(
    doc_id: str, request: Request, db: Session = Depends(get_db)
) -> EventSourceResponse:
    """Validate the persisted DMRL and stream PMC generation progress."""
    _require(db, doc_id)
    demo_mode = is_demo_mode(db)

    def work(progress: Progress) -> dict:
        progress.emit("validation_started", {"document_id": doc_id})
        session = open_session(demo_mode)
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
                if not is_pm_title(entry) and not entry.dmc:
                    raise AppError("DMRL_MISSING_DMC", f"DMC manquant à la ligne {index}.", 422)
                entries.append(entry)
                progress("validated", index * 100 // max(total, 1))
                progress.emit("validation_step", {"step": "validated", "current": index, "total": total})

            xml = generate_pmc(entries, pm_title=document.filename)
            progress.emit("pmc_generated", {"document_id": doc_id, "entries": total})
            return {"document_id": doc_id, "entries": total, "pmc": xml}
        finally:
            session.close()

    return stream_threaded_job(
        request,
        work,
        session_data={"document_id": doc_id},
        error_code="PMC_GENERATION_FAILED",
    )
