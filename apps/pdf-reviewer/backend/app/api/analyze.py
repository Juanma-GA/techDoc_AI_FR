"""POST /api/v1/documents/{id}/analyze — SSE stream emitting suggestions."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.errors import AppError
from app.core.pdf_versioning import current_path, path_for  # noqa: F401
from app.core.rules_engine import materialize, run_all
from app.db.models import AnalysisRun, Document, StandardVersion, Suggestion
from app.db.session import SessionLocal, get_db
from app.parsers.pdf_parser import parse_pdf
from app.schemas import SuggestionOut


router = APIRouter(tags=["analyze"])


@router.post("/documents/{document_id}/analyze")
def analyze_stream(
    document_id: uuid.UUID,
    vision: Optional[bool] = Query(
        default=None,
        description=(
            "Override per-run vision (Pixtral) opt-in/out. None = use the "
            "persisted `vision.enabled` setting from /settings/mistral."
        ),
    ),
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    # Run on the current version (post-edit) so the user can re-run the
    # analysis after applying suggestions and pick up new issues that the
    # edit may have introduced (or simply check that fixes hold).
    src = current_path(doc.storage_dir, doc.current_version)
    if not src.is_file():
        raise AppError("PDF_VERSION_MISSING", "PDF courant absent", status_code=500)

    # Drop transient suggestions from prior runs but PRESERVE the ones
    # already applied — the user can still undo them, and EditHistory needs
    # the row to render the undo button. Open / rejected / edited are
    # superseded by the fresh run so we wipe them.
    from sqlalchemy import delete

    db.execute(
        delete(Suggestion).where(
            Suggestion.document_id == document_id,
            Suggestion.status != "applied",
        )
    )
    sv_id = doc.standard_version_id
    # v2 multi-norm: parse the JSON list, fall back to the legacy single FK.
    try:
        sv_ids_list = json.loads(doc.standard_version_ids or "[]")
        if not isinstance(sv_ids_list, list):
            sv_ids_list = []
    except (ValueError, TypeError):
        sv_ids_list = []
    if not sv_ids_list and sv_id is not None:
        sv_ids_list = [str(sv_id)]
    run = AnalysisRun(
        document_id=document_id,
        standard_version_id=sv_id,
        standard_version_ids=json.dumps(sv_ids_list),
        status="running",
    )
    db.add(run)
    # Mark the document as analyzing immediately so the UI list reflects
    # the in-progress state (poll-driven badge update).
    doc.status = "analyzing"
    db.commit()
    db.refresh(run)

    document_id_value = document_id
    run_id_value = run.id
    src_path = str(src)
    target_unit = doc.target_unit_system
    sv_ids_value = sv_ids_list
    vision_override_value = vision  # captured for the worker thread

    async def event_gen():
        yield {
            "event": "run_started",
            "data": json.dumps({"run_id": str(run_id_value), "document_id": str(document_id_value)}),
        }

        try:
            yield {"event": "progress", "data": json.dumps({"step": "parse", "pct": 5})}
            parsed = await asyncio.to_thread(parse_pdf, src_path)
            yield {"event": "progress", "data": json.dumps({"step": "parse", "pct": 30})}

            # Build a lightweight Document-like with target_unit_system (we
            # don't reuse the ORM session inside the worker thread).
            class _DocStub:
                target_unit_system = target_unit

            scoped_session: Session = SessionLocal()
            try:
                versions: list = []
                for raw_id in sv_ids_value:
                    try:
                        vid = uuid.UUID(str(raw_id))
                    except (ValueError, TypeError):
                        continue
                    sv = scoped_session.get(StandardVersion, vid)
                    if sv is not None:
                        versions.append(sv)
                raws = await asyncio.to_thread(
                    lambda: run_all(
                        parsed, _DocStub(), scoped_session, versions,  # type: ignore[arg-type]
                        src_path=src_path,
                        vision_enabled_override=vision_override_value,
                    )
                )
                yield {"event": "progress", "data": json.dumps({"step": "rules", "pct": 70})}
                rows = materialize(raws, parsed, document_id_value, run_id_value, src_path=src_path)
                total = 0
                for sug in rows:
                    scoped_session.add(sug)
                    scoped_session.commit()
                    scoped_session.refresh(sug)
                    payload = SuggestionOut.model_validate(sug).model_dump(mode="json")
                    yield {"event": "suggestion", "data": json.dumps(payload)}
                    total += 1

                run_row = scoped_session.get(AnalysisRun, run_id_value)
                if run_row is not None:
                    run_row.status = "done"
                    run_row.finished_at = datetime.now(timezone.utc)
                    run_row.summary = json.dumps({"total": total})
                    scoped_session.commit()

                doc_row = scoped_session.get(Document, document_id_value)
                if doc_row is not None:
                    doc_row.status = "analyzed"
                    scoped_session.commit()

                yield {
                    "event": "done",
                    "data": json.dumps({"total": total, "run_id": str(run_id_value)}),
                }
            finally:
                scoped_session.close()
        except AppError as exc:
            _mark_failed(document_id_value)
            yield {"event": "error", "data": json.dumps({"code": exc.code, "message": exc.message})}
        except Exception as exc:  # noqa: BLE001
            _mark_failed(document_id_value)
            yield {
                "event": "error",
                "data": json.dumps({"code": "INTERNAL_ERROR", "message": str(exc)}),
            }

    return EventSourceResponse(event_gen())


def _mark_failed(document_id: uuid.UUID) -> None:
    """Reset Document.status if the analyse run blew up — never leave a
    document stuck in `analyzing` for the UI poller."""
    s = SessionLocal()
    try:
        doc = s.get(Document, document_id)
        if doc is not None and doc.status == "analyzing":
            doc.status = "analysis_failed"
            s.commit()
    except Exception:  # noqa: BLE001
        s.rollback()
    finally:
        s.close()
