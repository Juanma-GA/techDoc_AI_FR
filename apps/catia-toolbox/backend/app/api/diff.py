"""Routes /api/v1/diff - comparaison de deux imports (pieces modifiees)."""

from __future__ import annotations

import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import load_parsed_nodes
from app.core import diff_engine
from app.core.errors import AppError
from app.db.models import DiffEntry, DiffRun, StructureImport
from app.db.session import get_db
from app.schemas import DiffEntryOut, DiffIn, DiffRunOut


router = APIRouter(tags=["diff"])


def _require_import(db: Session, import_id: uuid.UUID) -> StructureImport:
    imp = db.get(StructureImport, import_id)
    if imp is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})
    return imp


@router.post("/diff", response_model=DiffRunOut)
def create_diff(body: DiffIn, db: Session = Depends(get_db)) -> DiffRun:
    if body.base_import_id == body.other_import_id:
        raise AppError(
            "COMPARE_SAME_IMPORT",
            "Selectionnez deux imports differents.",
            status_code=400,
        )
    _require_import(db, body.base_import_id)
    _require_import(db, body.other_import_id)
    base_nodes, _ = load_parsed_nodes(db, body.base_import_id)
    other_nodes, _ = load_parsed_nodes(db, body.other_import_id)
    entries = diff_engine.compare(base_nodes, other_nodes)
    summary = diff_engine.summarize(entries)

    run = DiffRun(
        base_import_id=body.base_import_id,
        other_import_id=body.other_import_id,
        summary=json.dumps(summary, ensure_ascii=False),
    )
    db.add(run)
    db.flush()
    for e in entries:
        db.add(DiffEntry(run_id=run.id, rel_path=e["rel_path"][:1000], change_type=e["change_type"], detail=e["detail"]))
    db.commit()
    db.refresh(run)
    return run


@router.get("/imports/{import_id}/diffs", response_model=list[DiffRunOut])
def list_diffs(import_id: uuid.UUID, db: Session = Depends(get_db)) -> list[DiffRun]:
    return list(
        db.scalars(
            select(DiffRun).where(DiffRun.base_import_id == import_id).order_by(DiffRun.created_at.desc())
        )
    )


@router.get("/diff/{run_id}/entries", response_model=list[DiffEntryOut])
def list_entries(
    run_id: uuid.UUID,
    change_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[DiffEntry]:
    if db.get(DiffRun, run_id) is None:
        raise AppError("DIFF_NOT_FOUND", "Comparaison introuvable.", status_code=404, detail={"id": str(run_id)})
    stmt = select(DiffEntry).where(DiffEntry.run_id == run_id)
    if change_type:
        stmt = stmt.where(DiffEntry.change_type == change_type)
    return list(db.scalars(stmt.order_by(DiffEntry.change_type, DiffEntry.rel_path)))


@router.get("/diff/{run_id}/export.csv")
def export_diff(run_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    run = db.get(DiffRun, run_id)
    if run is None:
        raise AppError("DIFF_NOT_FOUND", "Comparaison introuvable.", status_code=404, detail={"id": str(run_id)})
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["rel_path", "change_type", "detail"])
    for e in run.entries:
        w.writerow([e.rel_path, e.change_type, e.detail])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=diff_{str(run_id)[:8]}.csv"},
    )
