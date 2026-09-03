"""POST /api/v1/documents/{id}/analyze — SSE stream emitting suggestions."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from queue import Empty, SimpleQueue

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
    checklist: bool = Query(
        default=True,
        description="Cible checklist : quand false, exclut les regles importees (llm_nl/manual) du run.",
    ),
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    # Run on the current version (post-edit) so the user can re-run the
    # analysis after applying suggestions and pick up new issues that the
    # edit may have introduced (or simply check that fixes hold). Le chemin
    # depend du pipeline : .pdf (defaut) ou .docx (pipeline Word natif).
    is_docx = doc.working_format == "docx"
    if is_docx:
        from app.core import docx_versioning

        src = docx_versioning.version_path(doc.storage_dir, doc.current_version)
        if not src.is_file():
            raise AppError("DOCX_VERSION_MISSING", "DOCX courant absent", status_code=500)
    else:
        src = current_path(doc.storage_dir, doc.current_version)
        if not src.is_file():
            raise AppError("PDF_VERSION_MISSING", "PDF courant absent", status_code=500)

    # Rejection memory (corpus-agent-style): capture the signatures of every
    # finding the reviewer previously *rejected* on THIS document, so the same
    # false positive is not re-surfaced on re-analysis. Signature = (rule_code,
    # original_text) — the verbatim span text is exact enough on a PDF. Empty
    # original_text (absence-type findings) can't be matched reliably → skipped.
    from sqlalchemy import delete, select as _select

    rejected_rows = db.execute(
        _select(Suggestion.rule_code, Suggestion.original_text).where(
            Suggestion.document_id == document_id,
            Suggestion.status == "rejected",
        )
    ).all()
    rejected_sigs: set[tuple[str, str]] = {(rc, ot) for rc, ot in rejected_rows if ot}

    # Drop transient suggestions from prior runs but PRESERVE the ones already
    # applied (undo needs the row) AND the ones rejected (they feed the memory
    # above and must persist their motif). Open / edited / accepted are
    # superseded by the fresh run so we wipe them.
    db.execute(
        delete(Suggestion).where(
            Suggestion.document_id == document_id,
            Suggestion.status.notin_(("applied", "rejected")),
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
    # Portail qualite : etat de revuabilite (homogene tous formats), signale en
    # tete de flux pour qu'un document non exploitable (scan sans couche texte)
    # ne rende pas une revue vide silencieuse.
    quality_value = doc.quality
    coverage_value = doc.text_coverage
    convert_engine_value = doc.convert_engine
    sv_ids_value = sv_ids_list
    vision_override_value = vision  # captured for the worker thread
    checklist_enabled_value = checklist  # captured for the worker thread
    rejected_sigs_value = rejected_sigs  # captured for the worker thread
    is_docx_value = is_docx  # pipeline Word natif vs PDF
    # Mapping manuel du document (cf. rules_engine._doc_meta_block) — capture
    # avant d'entrer dans le worker thread (pas de reutilisation de session ORM).
    meta_revision_date_value = doc.meta_revision_date
    meta_cmm_number_value = doc.meta_cmm_number
    meta_first_issue_date_value = doc.meta_first_issue_date
    meta_revision_number_value = doc.meta_revision_number

    async def event_gen():
        yield {
            "event": "run_started",
            "data": json.dumps({"run_id": str(run_id_value), "document_id": str(document_id_value)}),
        }
        yield {
            "event": "quality",
            "data": json.dumps({
                "state": quality_value,
                "coverage": coverage_value,
                "engine": convert_engine_value,
            }),
        }

        try:
            yield {"event": "progress", "data": json.dumps({"step": "parse", "pct": 5})}
            if is_docx_value:
                from app.parsers.docx_parser import parse_docx

                parsed = await asyncio.to_thread(parse_docx, src_path)
            else:
                parsed = await asyncio.to_thread(parse_pdf, src_path)
            yield {"event": "progress", "data": json.dumps({"step": "parse", "pct": 30})}

            # Build a lightweight Document-like with target_unit_system (we
            # don't reuse the ORM session inside the worker thread).
            class _DocStub:
                target_unit_system = target_unit
                meta_revision_date = meta_revision_date_value
                meta_cmm_number = meta_cmm_number_value
                meta_first_issue_date = meta_first_issue_date_value
                meta_revision_number = meta_revision_number_value

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

                # Le scan checklist/IA (une passe Mistral par page) domine
                # generalement le temps d'une analyse : sans remontee de
                # progression pendant ce calcul (execute dans un thread), la
                # jauge restait figee puis sautait directement a la fin,
                # donnant l'impression qu'elle "disparaissait". `progress_q`
                # relie le callback (appele depuis le thread) au generateur
                # SSE (event loop) via `call_soon_threadsafe`.
                progress_q: "SimpleQueue[int]" = SimpleQueue()
                loop = asyncio.get_running_loop()

                def _on_progress(pct: int) -> None:
                    loop.call_soon_threadsafe(progress_q.put_nowait, pct)

                # Echecs du scan checklist/IA (Mistral mal configure, quota,
                # modele invalide sur un endpoint prive…) : remontes ici au
                # lieu de se traduire silencieusement par "0 anomalie" (HR7).
                run_warnings: list[str] = []

                if is_docx_value:
                    from app.core import docx_pipeline

                    task = asyncio.create_task(
                        asyncio.to_thread(
                            lambda: docx_pipeline.run_docx(
                                parsed, _DocStub(), scoped_session, versions,  # type: ignore[arg-type]
                                checklist_enabled=checklist_enabled_value,
                                progress_cb=_on_progress,
                                warnings=run_warnings,
                            )
                        )
                    )
                    while not task.done():
                        try:
                            pct = progress_q.get_nowait()
                            yield {"event": "progress", "data": json.dumps({"step": "rules", "pct": pct})}
                        except Empty:
                            await asyncio.sleep(0.2)
                    raws = await task
                    yield {"event": "progress", "data": json.dumps({"step": "rules", "pct": 70})}
                    rows = docx_pipeline.materialize_docx(
                        raws, parsed, document_id_value, run_id_value
                    )
                else:
                    task = asyncio.create_task(
                        asyncio.to_thread(
                            lambda: run_all(
                                parsed, _DocStub(), scoped_session, versions,  # type: ignore[arg-type]
                                src_path=src_path,
                                vision_enabled_override=vision_override_value,
                                checklist_enabled=checklist_enabled_value,
                                progress_cb=_on_progress,
                                warnings=run_warnings,
                            )
                        )
                    )
                    while not task.done():
                        try:
                            pct = progress_q.get_nowait()
                            yield {"event": "progress", "data": json.dumps({"step": "rules", "pct": pct})}
                        except Empty:
                            await asyncio.sleep(0.2)
                    raws = await task
                    yield {"event": "progress", "data": json.dumps({"step": "rules", "pct": 70})}
                    rows = materialize(raws, parsed, document_id_value, run_id_value, src_path=src_path)

                if run_warnings:
                    yield {"event": "warning", "data": json.dumps({"messages": run_warnings})}

                total = 0
                suppressed_rejected = 0
                for sug in rows:
                    # Rejection memory: suppress a re-detection the reviewer
                    # already rejected on this document (same rule_code + text).
                    if (sug.rule_code, sug.original_text) in rejected_sigs_value:
                        suppressed_rejected += 1
                        continue
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
                    run_row.summary = json.dumps(
                        {"total": total, "suppressed_rejected": suppressed_rejected}
                    )
                    scoped_session.commit()

                doc_row = scoped_session.get(Document, document_id_value)
                if doc_row is not None:
                    doc_row.status = "analyzed"
                    scoped_session.commit()

                yield {
                    "event": "done",
                    "data": json.dumps({
                        "total": total,
                        "suppressed_rejected": suppressed_rejected,
                        "run_id": str(run_id_value),
                    }),
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
