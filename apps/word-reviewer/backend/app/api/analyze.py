"""Route /api/v1/documents/{id}/analyze - analyse en streaming SSE.

Events : `session` (init avec run_id + compteurs) -> `suggestion`* (chaque
finding) -> `done` (resume) ou `error`. Endpoint POST uniquement (l'EventSource
natif refuse POST -> cote client : fetch + ReadableStream).

Pour le lot deterministe : le travail (run_all + materialize) est fait de maniere
synchrone, puis les findings sont diffuses. Les couches LLM (verif adversariale,
budget) se brancheront ici au lot fiabilisation.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core import feedback, llm_checks, rules_engine
from app.core import docx_versioning as ver
from app.core.docx_zones import recognize_zones
from app.core.errors import AppError
from app.db.models import AnalysisRun, Document, StandardVersion, Suggestion
from app.db.session import get_db
from app.parsers.docx_parser import parse_docx
from app.schemas import AnalyzeRequest, SuggestionOut


log = logging.getLogger("word_reviewer.analyze")

router = APIRouter(prefix="/documents", tags=["analyze"])


def _resolve_version_ids(doc: Document, payload: AnalyzeRequest) -> list[uuid.UUID]:
    if payload.standard_version_ids:
        return payload.standard_version_ids
    try:
        return [uuid.UUID(x) for x in json.loads(doc.standard_version_ids or "[]")]
    except (ValueError, TypeError):
        return []


@router.post("/{document_id}/analyze")
async def analyze(
    document_id: uuid.UUID,
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("NOT_FOUND", "Document introuvable.", 404)

    version_ids = _resolve_version_ids(doc, payload)
    versions = list(
        db.scalars(select(StandardVersion).where(StandardVersion.id.in_(version_ids)))
    ) if version_ids else []

    try:
        parsed = recognize_zones(parse_docx(ver.version_path(doc.storage_dir, doc.current_version)))
    except Exception as exc:  # noqa: BLE001
        raise AppError("BAD_DOCX", "Document illisible pour l'analyse.", 400) from exc

    # Lecture (rapide) hors stream : checks deterministes + construction des regles.
    # On NE tient PAS de transaction d'ecriture pendant la passe LLM (lente) sinon
    # le verrou SQLite bloque les autres ecritures (ex. ajout de regle).
    exclusions = feedback.load_exclusions(db)
    rules = rules_engine.build_rules(db, versions)
    det_raws = rules_engine.run_all(parsed, doc, db, versions)

    async def event_stream():
        try:
            # Demarrage immediat : l'UI sait que ca travaille avant le 1er appel LLM.
            yield {"event": "session", "data": json.dumps({"phase": "start"})}

            # --- Passe LLM, progression diffusee morceau par morceau ---
            llm_raws = []
            try:
                async for ev in llm_checks.run_llm_iter(db, parsed, rules):
                    if ev["type"] in {"start", "progress"}:
                        yield {"event": "progress", "data": json.dumps(
                            {"done": ev.get("done", 0), "total": ev["total"]}
                        )}
                    elif ev["type"] == "result":
                        llm_raws = ev["survivors"]
            except Exception as exc:  # noqa: BLE001
                log.warning("LLM pass failed, deterministic only: %s", exc)
                llm_raws = []

            raws = rules_engine.dedupe(det_raws + llm_raws)
            raws = feedback.filter_excluded(raws, exclusions)

            # --- Phase ECRITURE (courte) ---
            db.execute(delete(Suggestion).where(Suggestion.document_id == doc.id))
            run = AnalysisRun(
                document_id=doc.id,
                standard_version_ids=json.dumps([str(i) for i in version_ids]),
                status="running",
            )
            db.add(run)
            db.flush()
            rows = rules_engine.materialize(db, doc, run, raws)
            db.flush()

            by_severity: dict[str, int] = {}
            by_kind: dict[str, int] = {}
            for r in rows:
                by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
                by_kind[r.rule_kind] = by_kind.get(r.rule_kind, 0) + 1
            summary = {"total": len(rows), "by_severity": by_severity, "by_kind": by_kind}

            run.status = "completed"
            run.finished_at = datetime.now(timezone.utc)
            run.summary = json.dumps(summary)
            doc.status = "analyzed"
            out = [SuggestionOut.model_validate(r) for r in rows]
            db.commit()

            yield {"event": "session", "data": json.dumps({"run_id": str(run.id), "total": len(out)})}
            for s in out:
                yield {"event": "suggestion", "data": s.model_dump_json()}
            yield {"event": "done", "data": json.dumps(summary)}
        except Exception as exc:  # noqa: BLE001
            log.exception("analyze failed")
            db.rollback()
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(event_stream())
