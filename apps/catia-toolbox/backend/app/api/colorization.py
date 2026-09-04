"""Routes /api/v1 - colorisation des pieces (par etat / type / profondeur)."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import load_parsed_nodes
from app.core import colorize_engine
from app.core.errors import AppError
from app.db.models import ColorizationItem, ColorizationRun, DiffEntry, DiffRun, StructureImport
from app.db.session import get_db
from app.schemas import ColorizationIn, ColorizationItemOut, ColorizationRunOut


router = APIRouter(tags=["colorization"])


@router.get("/colorization/strategies", response_model=list[str])
def strategies() -> list[str]:
    return colorize_engine.STRATEGIES


@router.post("/imports/{import_id}/colorization", response_model=ColorizationRunOut)
def create_colorization(import_id: uuid.UUID, body: ColorizationIn, db: Session = Depends(get_db)) -> ColorizationRun:
    if db.get(StructureImport, import_id) is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})

    strategy = body.strategy if body.strategy in colorize_engine.STRATEGIES else "by_type"

    if strategy == "by_change":
        if body.diff_run_id is None:
            raise AppError(
                "COLOR_DIFF_REQUIRED",
                "La strategie by_change requiert diff_run_id (une comparaison).",
                status_code=400,
            )
        diff = db.get(DiffRun, body.diff_run_id)
        if diff is None:
            raise AppError("DIFF_NOT_FOUND", "Comparaison introuvable.", status_code=404, detail={"id": str(body.diff_run_id)})
        entries = db.scalars(select(DiffEntry).where(DiffEntry.run_id == body.diff_run_id))
        items = colorize_engine.colorize_by_change(
            [{"rel_path": e.rel_path, "change_type": e.change_type} for e in entries]
        )
    else:
        nodes, _ = load_parsed_nodes(db, import_id)
        items = (
            colorize_engine.colorize_by_type(nodes)
            if strategy == "by_type"
            else colorize_engine.colorize_by_depth(nodes)
        )

    summary = colorize_engine.summarize(items)
    run = ColorizationRun(
        import_id=import_id,
        diff_run_id=body.diff_run_id if strategy == "by_change" else None,
        strategy=strategy,
        config_json=json.dumps({"strategy": strategy}, ensure_ascii=False),
        summary=json.dumps(summary, ensure_ascii=False),
    )
    db.add(run)
    db.flush()
    for it in items:
        db.add(
            ColorizationItem(
                run_id=run.id,
                rel_path=it["rel_path"][:1000],
                color_r=it["r"],
                color_g=it["g"],
                color_b=it["b"],
                reason=it["reason"],
            )
        )
    db.commit()
    db.refresh(run)
    return run


@router.get("/imports/{import_id}/colorizations", response_model=list[ColorizationRunOut])
def list_colorizations(import_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ColorizationRun]:
    return list(
        db.scalars(
            select(ColorizationRun)
            .where(ColorizationRun.import_id == import_id)
            .order_by(ColorizationRun.created_at.desc())
        )
    )


@router.get("/colorizations/{run_id}/items", response_model=list[ColorizationItemOut])
def list_items(run_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ColorizationItem]:
    if db.get(ColorizationRun, run_id) is None:
        raise AppError("COLORIZATION_NOT_FOUND", "Colorisation introuvable.", status_code=404, detail={"id": str(run_id)})
    return list(
        db.scalars(select(ColorizationItem).where(ColorizationItem.run_id == run_id).order_by(ColorizationItem.rel_path))
    )


@router.get("/colorizations/{run_id}/export.csv")
def export_csv(run_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    run = db.get(ColorizationRun, run_id)
    if run is None:
        raise AppError("COLORIZATION_NOT_FOUND", "Colorisation introuvable.", status_code=404, detail={"id": str(run_id)})
    content = colorize_engine.to_csv(run.items)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=colorisation_{str(run_id)[:8]}.csv"},
    )


@router.get("/colorizations/{run_id}/simulation.svg")
def simulation_svg(run_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    run = db.get(ColorizationRun, run_id)
    if run is None:
        raise AppError("COLORIZATION_NOT_FOUND", "Colorisation introuvable.", status_code=404, detail={"id": str(run_id)})
    svg = colorize_engine.to_svg(list(run.items))
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/colorizations/{run_id}/export.macro")
def export_macro(run_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Macro CATIA V5 (VBScript SetRealColor) - dry-run."""
    run = db.get(ColorizationRun, run_id)
    if run is None:
        raise AppError("COLORIZATION_NOT_FOUND", "Colorisation introuvable.", status_code=404, detail={"id": str(run_id)})
    content = colorize_engine.to_macro(run.items)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=colorisation_{str(run_id)[:8]}.CATScript"},
    )


@router.get("/colorizations/{run_id}/export.composer.py")
def export_composer(run_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Script Python win32com colorisant les acteurs Composer (DRY_RUN par defaut)."""
    run = db.get(ColorizationRun, run_id)
    if run is None:
        raise AppError("COLORIZATION_NOT_FOUND", "Colorisation introuvable.", status_code=404, detail={"id": str(run_id)})
    content = colorize_engine.to_composer_pyscript(run.items)
    return Response(
        content=content,
        media_type="text/x-python; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=colorisation_composer_{str(run_id)[:8]}.py"},
    )
