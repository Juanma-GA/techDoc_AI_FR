"""Routes /api/v1/imports/{id}/optimize - generation du plan (SSE).

Events SSE : session -> token* -> done | error (convention STANDARD §14).
Le generateur ouvre une session DB FRAICHE (jamais celle du Depends, qui est
fermee a la fin de la requete avant que le stream ne soit consomme).
"""

from __future__ import annotations

import json
import logging
import traceback
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.errors import AppError
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled
from app.core.optimizer_engine import (
    build_baseline_suggestions,
    parse_suggestions_from_text,
    stream_plan,
)
from app.core.parser import ParsedNode
from app.db.models import OptimizationRun, StructureImport, Suggestion, TreeNode
from app.db.session import SessionLocal, get_db
from app.schemas import OptimizationRunOut, OptimizeIn


log = logging.getLogger("catia_toolbox.optimize")

router = APIRouter(prefix="/imports", tags=["optimize"])


def _nodes_as_parsed(db: Session, import_id: uuid.UUID) -> tuple[list[ParsedNode], dict[str, uuid.UUID]]:
    rows = list(db.scalars(select(TreeNode).where(TreeNode.import_id == import_id)))
    nodes: list[ParsedNode] = []
    id_by_path: dict[str, uuid.UUID] = {}
    for r in rows:
        id_by_path[r.rel_path] = r.id
        parent_path = r.rel_path.rsplit("/", 1)[0] if "/" in r.rel_path else None
        nodes.append(
            ParsedNode(
                rel_path=r.rel_path,
                name=r.name,
                ext=r.ext,
                kind=r.kind,
                depth=r.depth,
                size=r.size,
                mtime=r.mtime,
                parent_path=parent_path,
            )
        )
    return nodes, id_by_path


def _dedup(suggestions: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for s in suggestions:
        key = (s["old_path"], s["new_path"])
        if key in seen or s["old_path"] == s["new_path"]:
            continue
        seen.add(key)
        out.append(s)
    return out


def _persist_suggestions(
    db: Session, run: OptimizationRun, suggestions: list[dict], id_by_path: dict[str, uuid.UUID]
) -> dict[str, int]:
    counts: dict[str, int] = {"move": 0, "rename": 0, "group": 0, "keep": 0, "llm": 0, "baseline": 0}
    for s in suggestions:
        db.add(
            Suggestion(
                run_id=run.id,
                node_id=id_by_path.get(s.get("node_rel_path") or s["old_path"]),
                old_path=s["old_path"][:1000],
                new_path=s["new_path"][:1000],
                action=s["action"],
                rationale=s.get("rationale", ""),
                confidence=s.get("confidence", "moyenne"),
                source=s.get("source", "llm"),
            )
        )
        counts[s["action"]] = counts.get(s["action"], 0) + 1
        counts[s.get("source", "llm")] = counts.get(s.get("source", "llm"), 0) + 1
    counts["total"] = len(suggestions)
    return counts


@router.get("/{import_id}/optimize/runs", response_model=list[OptimizationRunOut])
def list_runs(import_id: uuid.UUID, db: Session = Depends(get_db)) -> list[OptimizationRunOut]:
    rows = db.scalars(
        select(OptimizationRun)
        .where(OptimizationRun.import_id == import_id)
        .order_by(OptimizationRun.started_at.desc())
    )
    return [
        OptimizationRunOut(
            id=r.id,
            import_id=r.import_id,
            status=r.status,
            summary=json.loads(r.summary or "{}"),
            started_at=r.started_at,
            finished_at=r.finished_at,
        )
        for r in rows
    ]


@router.post("/{import_id}/optimize")
async def optimize(import_id: uuid.UUID, body: OptimizeIn, db: Session = Depends(get_db)):
    imp = db.get(StructureImport, import_id)
    if imp is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})

    config = {"target_max_depth": body.target_max_depth, "strategy": body.strategy, "use_llm": body.use_llm}

    # Mistral optionnel : si absent ou interrupteur OFF, on bascule en baseline-only.
    mistral: MistralClient | None = None
    if body.use_llm and not get_llm_enabled(db):
        config["llm_fallback"] = "disabled"
    elif body.use_llm:
        try:
            mistral = MistralClient.from_db(db)
        except MistralError:
            mistral = None
            config["llm_fallback"] = "not_configured"

    run = OptimizationRun(import_id=import_id, status="running", config_json=json.dumps(config))
    db.add(run)
    db.commit()
    db.refresh(run)

    run_id = run.id
    root_label = imp.root_label

    async def event_gen():
        stream_db = SessionLocal()
        try:
            s_run = stream_db.get(OptimizationRun, run_id)
            if s_run is None:
                yield {"event": "error", "data": json.dumps({"message": "Run perdu."})}
                return

            yield {"event": "session", "data": json.dumps({"run_id": str(run_id), "title": root_label})}

            nodes, id_by_path = _nodes_as_parsed(stream_db, import_id)
            metrics = json.loads(stream_db.get(StructureImport, import_id).metrics_json or "{}")
            sample_paths = [n.rel_path for n in nodes if n.kind == "file"]

            baseline = build_baseline_suggestions(nodes, metrics, config)
            llm_suggestions: list[dict] = []

            try:
                if mistral is not None:
                    acc = ""
                    async for delta in stream_plan(mistral, metrics, sample_paths, config):
                        acc += delta
                        yield {"event": "token", "data": delta}
                    llm_suggestions = parse_suggestions_from_text(acc)
                else:
                    msg = (
                        "Mistral non configure : generation du plan baseline "
                        "(heuristiques deterministes) uniquement."
                    )
                    yield {"event": "token", "data": msg}

                combined = _dedup(llm_suggestions + baseline)
                counts = _persist_suggestions(stream_db, s_run, combined, id_by_path)
                s_run.status = "completed"
                s_run.summary = json.dumps(counts, ensure_ascii=False)
                s_run.finished_at = datetime.now(timezone.utc)
                stream_db.commit()
                yield {"event": "done", "data": json.dumps(counts)}
            except Exception as e:  # noqa: BLE001
                log.error("optimize error: %s\n%s", e, traceback.format_exc())
                s_run.status = "failed"
                s_run.finished_at = datetime.now(timezone.utc)
                stream_db.commit()
                yield {"event": "error", "data": json.dumps({"message": f"{type(e).__name__}: {e}"})}
        finally:
            stream_db.close()

    return EventSourceResponse(event_gen())
