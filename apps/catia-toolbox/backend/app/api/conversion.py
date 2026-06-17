"""Routes /api/v1 - plan de conversion CATIA 3D -> Composer (dry-run)."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import load_parsed_nodes
from app.core import conversion_planner
from app.core.errors import AppError
from app.db.models import ConversionItem, ConversionRun, StructureImport
from app.db.session import get_db
from app.schemas import ConversionIn, ConversionItemOut, ConversionRunOut


router = APIRouter(tags=["conversion"])


@router.post("/imports/{import_id}/conversion", response_model=ConversionRunOut)
def create_conversion(import_id: uuid.UUID, body: ConversionIn, db: Session = Depends(get_db)) -> ConversionRun:
    if db.get(StructureImport, import_id) is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})
    nodes, _ = load_parsed_nodes(db, import_id)
    items = conversion_planner.plan(nodes, target_dir=body.target_dir, target_ext=body.target_ext)
    summary = conversion_planner.summarize(items)

    run = ConversionRun(
        import_id=import_id,
        config_json=json.dumps(body.model_dump(), ensure_ascii=False),
        summary=json.dumps(summary, ensure_ascii=False),
    )
    db.add(run)
    db.flush()
    for it in items:
        db.add(
            ConversionItem(
                run_id=run.id,
                source_path=it["source_path"][:1000],
                target_path=it["target_path"][:1000],
                source_ext=it["source_ext"][:40],
            )
        )
    db.commit()
    db.refresh(run)
    return run


@router.get("/imports/{import_id}/conversions", response_model=list[ConversionRunOut])
def list_conversions(import_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ConversionRun]:
    return list(
        db.scalars(
            select(ConversionRun).where(ConversionRun.import_id == import_id).order_by(ConversionRun.created_at.desc())
        )
    )


@router.get("/conversions/{run_id}/items", response_model=list[ConversionItemOut])
def list_items(run_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ConversionItem]:
    if db.get(ConversionRun, run_id) is None:
        raise AppError("CONVERSION_NOT_FOUND", "Conversion introuvable.", status_code=404, detail={"id": str(run_id)})
    return list(
        db.scalars(select(ConversionItem).where(ConversionItem.run_id == run_id).order_by(ConversionItem.source_path))
    )


@router.get("/conversions/{run_id}/export.csv")
def export_csv(run_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    run = db.get(ConversionRun, run_id)
    if run is None:
        raise AppError("CONVERSION_NOT_FOUND", "Conversion introuvable.", status_code=404, detail={"id": str(run_id)})
    content = conversion_planner.to_csv(run.items)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=conversion_{str(run_id)[:8]}.csv"},
    )


@router.get("/conversions/{run_id}/export.script")
def export_script(run_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Script Python win32com pilotant Composer (DRY_RUN par defaut)."""
    run = db.get(ConversionRun, run_id)
    if run is None:
        raise AppError("CONVERSION_NOT_FOUND", "Conversion introuvable.", status_code=404, detail={"id": str(run_id)})
    content = conversion_planner.to_pyscript(run.items)
    return Response(
        content=content,
        media_type="text/x-python; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=conversion_composer_{str(run_id)[:8]}.py"},
    )
