"""Routes /api/v1 - plan de remplacement de pieces (dry-run)."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from pathlib import Path

from app.api.deps import load_parsed_nodes
from app.config import settings
from app.core import onedrive, replacement_planner
from app.core.errors import AppError
from app.core.security import read_and_validate, safe_under_root
from app.db.models import ReplacementItem, ReplacementRun, StructureImport
from app.db.session import get_db
from app.schemas import ReplacementFromSourceIn, ReplacementItemOut, ReplacementRunOut


router = APIRouter(tags=["replacement"])

_MAPPING_EXTS = {".csv", ".json"}


def _build_replacement(db: Session, import_id: uuid.UUID, raw: bytes, ext: str) -> ReplacementRun:
    """Coeur commun : parse le mapping, calcule le plan, persiste le run."""
    if db.get(StructureImport, import_id) is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})
    mapping = replacement_planner.parse_mapping(raw, ext)
    nodes, _ = load_parsed_nodes(db, import_id)
    items = replacement_planner.plan(nodes, mapping)
    summary = replacement_planner.summarize(items)

    run = ReplacementRun(
        import_id=import_id,
        mapping_json=json.dumps(mapping, ensure_ascii=False),
        summary=json.dumps(summary, ensure_ascii=False),
    )
    db.add(run)
    db.flush()
    for it in items:
        db.add(
            ReplacementItem(
                run_id=run.id,
                occurrence_path=it["occurrence_path"][:1000],
                old_ref=it["old_ref"][:500],
                new_ref=it["new_ref"][:500],
            )
        )
    db.commit()
    db.refresh(run)
    return run


@router.post("/imports/{import_id}/replacement", response_model=ReplacementRunOut)
def create_replacement(
    import_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ReplacementRun:
    raw, _name, ext = read_and_validate(file, max_size=settings.max_upload_size_bytes, allowed_exts=_MAPPING_EXTS)
    return _build_replacement(db, import_id, raw, ext)


@router.post("/imports/{import_id}/replacement/source", response_model=ReplacementRunOut)
def create_replacement_from_source(
    import_id: uuid.UUID,
    payload: ReplacementFromSourceIn,
    db: Session = Depends(get_db),
) -> ReplacementRun:
    """Mapping choisi directement dans la Source (CSV/JSON), au lieu d'un upload."""
    if payload.scope not in ("input", "output"):
        raise AppError("SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)
    root = onedrive.root_for_scope(db, payload.scope)
    target = safe_under_root(root, payload.path)
    if not target.is_file():
        raise AppError("MAPPING_NOT_FOUND", "Fichier mapping introuvable.", status_code=404, detail={"path": str(target)})
    ext = target.suffix.lower()
    if ext not in _MAPPING_EXTS:
        raise AppError("MAPPING_EXT_INVALID", "Mapping attendu : .csv ou .json.", status_code=400, detail={"ext": ext})
    raw = target.read_bytes()
    return _build_replacement(db, import_id, raw, ext)


@router.get("/imports/{import_id}/replacements", response_model=list[ReplacementRunOut])
def list_replacements(import_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ReplacementRun]:
    return list(
        db.scalars(
            select(ReplacementRun).where(ReplacementRun.import_id == import_id).order_by(ReplacementRun.created_at.desc())
        )
    )


@router.get("/replacements/{run_id}/items", response_model=list[ReplacementItemOut])
def list_items(run_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ReplacementItem]:
    if db.get(ReplacementRun, run_id) is None:
        raise AppError("REPLACEMENT_NOT_FOUND", "Remplacement introuvable.", status_code=404, detail={"id": str(run_id)})
    return list(
        db.scalars(select(ReplacementItem).where(ReplacementItem.run_id == run_id).order_by(ReplacementItem.old_ref))
    )


@router.get("/replacements/{run_id}/export.csv")
def export_csv(run_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    run = db.get(ReplacementRun, run_id)
    if run is None:
        raise AppError("REPLACEMENT_NOT_FOUND", "Remplacement introuvable.", status_code=404, detail={"id": str(run_id)})
    content = replacement_planner.to_csv(run.items)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=replacement_{str(run_id)[:8]}.csv"},
    )


@router.get("/replacements/{run_id}/export.macro")
def export_macro(run_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    run = db.get(ReplacementRun, run_id)
    if run is None:
        raise AppError("REPLACEMENT_NOT_FOUND", "Remplacement introuvable.", status_code=404, detail={"id": str(run_id)})
    content = replacement_planner.to_macro(run.items)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=replacement_{str(run_id)[:8]}.CATScript"},
    )
