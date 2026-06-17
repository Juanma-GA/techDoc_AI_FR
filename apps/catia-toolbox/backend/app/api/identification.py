"""Routes /api/v1/identification - Etape 1 : nomenclature .xlsm + DE .zip.

Lit le fichier nomenclature (confine sous la racine du scope) pour identifier
les CATPart a traiter (+ SIN mono-couleur pour l'etape 3). Liste aussi le
contenu d'un .zip de donnees d'entree (metadonnees seules).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import nomenclature as nomen
from app.core import onedrive
from app.core.errors import AppError
from app.core.security import safe_under_root
from app.db.models import NomenclatureItem, NomenclatureRun
from app.db.session import get_db
from app.schemas import (
    NomenclatureItemOut,
    NomenclatureParseIn,
    NomenclaturePreviewIn,
    NomenclaturePreviewOut,
    NomenclatureRunOut,
    ZipEntryOut,
    ZipListOut,
)


log = logging.getLogger("catia_toolbox.identification")

router = APIRouter(prefix="/identification", tags=["identification"])


def _run_out(run: NomenclatureRun) -> NomenclatureRunOut:
    return NomenclatureRunOut(
        id=run.id,
        source_ref=run.source_ref,
        sheet=run.sheet,
        status=run.status,
        summary=json.loads(run.summary or "{}"),
        created_at=run.created_at,
    )


@router.post("/nomenclature", response_model=NomenclatureRunOut)
def parse_route(payload: NomenclatureParseIn, db: Session = Depends(get_db)) -> NomenclatureRunOut:
    if payload.scope not in ("input", "output"):
        raise AppError("SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)
    root = onedrive.root_for_scope(db, payload.scope)
    target = safe_under_root(root, payload.path)
    if not target.is_file():
        raise AppError("NOMENCLATURE_NOT_FOUND", "Fichier nomenclature introuvable.", status_code=404, detail={"path": str(target)})

    result = nomen.parse_nomenclature(str(target), sheet=payload.sheet)

    run = NomenclatureRun(
        source_ref=str(target),
        sheet=result["sheet"][:200],
        status="completed",
        summary=json.dumps(result["summary"], ensure_ascii=False),
    )
    db.add(run)
    db.flush()
    for it in result["items"]:
        db.add(NomenclatureItem(run_id=run.id, **it))
    db.commit()
    db.refresh(run)
    log.info("nomenclature %s : %d lignes", run.id, result["summary"]["rows"])
    return _run_out(run)


@router.post("/preview", response_model=NomenclaturePreviewOut)
def preview_route(payload: NomenclaturePreviewIn, db: Session = Depends(get_db)) -> NomenclaturePreviewOut:
    """Apercu : liste les onglets + affiche les premieres lignes d'un onglet."""
    if payload.scope not in ("input", "output"):
        raise AppError("SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)
    root = onedrive.root_for_scope(db, payload.scope)
    target = safe_under_root(root, payload.path)
    if not target.is_file():
        raise AppError("NOMENCLATURE_NOT_FOUND", "Fichier introuvable.", status_code=404, detail={"path": str(target)})
    return NomenclaturePreviewOut(**nomen.preview_sheet(str(target), sheet=payload.sheet, rows=payload.rows))


@router.post("/zip", response_model=ZipListOut)
def list_zip_route(payload: NomenclatureParseIn, db: Session = Depends(get_db)) -> ZipListOut:
    if payload.scope not in ("input", "output"):
        raise AppError("SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)
    root = onedrive.root_for_scope(db, payload.scope)
    target = safe_under_root(root, payload.path)
    if not target.is_file():
        raise AppError("ZIP_NOT_FOUND", "Fichier .zip introuvable.", status_code=404, detail={"path": str(target)})
    entries = nomen.list_zip(str(target))
    return ZipListOut(
        path=str(target),
        count=len(entries),
        entries=[ZipEntryOut(**e) for e in entries],
    )


@router.get("", response_model=list[NomenclatureRunOut])
def list_runs(db: Session = Depends(get_db)) -> list[NomenclatureRunOut]:
    rows = db.scalars(select(NomenclatureRun).order_by(NomenclatureRun.created_at.desc()))
    return [_run_out(r) for r in rows]


@router.get("/{run_id}", response_model=NomenclatureRunOut)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> NomenclatureRunOut:
    run = db.get(NomenclatureRun, run_id)
    if run is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404)
    return _run_out(run)


@router.get("/{run_id}/items", response_model=list[NomenclatureItemOut])
def list_items(
    run_id: uuid.UUID,
    to_treat: bool | None = Query(default=None),
    mono_color: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[NomenclatureItemOut]:
    if db.get(NomenclatureRun, run_id) is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404)
    stmt = select(NomenclatureItem).where(NomenclatureItem.run_id == run_id)
    if to_treat is not None:
        stmt = stmt.where(NomenclatureItem.to_treat == to_treat)
    if mono_color is not None:
        stmt = stmt.where(NomenclatureItem.mono_color == mono_color)
    return list(db.scalars(stmt.order_by(NomenclatureItem.source_row)))


@router.get("/{run_id}/export.csv")
def export_csv(
    run_id: uuid.UUID,
    to_treat: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if db.get(NomenclatureRun, run_id) is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404)
    stmt = select(NomenclatureItem).where(NomenclatureItem.run_id == run_id)
    if to_treat is not None:
        stmt = stmt.where(NomenclatureItem.to_treat == to_treat)
    rows = list(db.scalars(stmt.order_by(NomenclatureItem.source_row)))

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["catpart", "designation", "sin", "version", "to_treat", "mono_color", "r", "g", "b"])
    for r in rows:
        w.writerow([r.catpart, r.designation, r.sin, r.version, int(r.to_treat), int(r.mono_color), r.color_r, r.color_g, r.color_b])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=catparts_{str(run_id)[:8]}.csv"},
    )


@router.delete("/{run_id}", status_code=204)
def delete_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    run = db.get(NomenclatureRun, run_id)
    if run is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404)
    db.delete(run)
    db.commit()
