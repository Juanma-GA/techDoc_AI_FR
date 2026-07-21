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
from app.core import nomenclature_diff as nomdiff
from app.core import onedrive
from app.core.errors import AppError
from app.core.security import safe_under_root
from app.db.models import NomenclatureItem, NomenclatureRun
from app.db.session import get_db
from app.schemas import (
    NomenclatureCompareIn,
    NomenclatureCompareOut,
    NomenclatureItemOut,
    NomenclatureParseIn,
    NomenclaturePreviewIn,
    NomenclaturePreviewOut,
    NomenclatureRunOut,
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

    mapping = payload.mapping.model_dump() if payload.mapping else None
    result = nomen.parse_nomenclature(str(target), sheet=payload.sheet, mapping=mapping)

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


@router.get("", response_model=list[NomenclatureRunOut])
def list_runs(db: Session = Depends(get_db)) -> list[NomenclatureRunOut]:
    rows = db.scalars(select(NomenclatureRun).order_by(NomenclatureRun.created_at.desc()))
    return [_run_out(r) for r in rows]


def _item_dict(it: NomenclatureItem) -> dict:
    return {
        "catpart": it.catpart,
        "designation": it.designation,
        "sin": it.sin,
        "version": it.version,
        "new_pn": it.new_pn,
        "new_rev": it.new_rev,
    }


def _load_compare(db: Session, base_run_id: uuid.UUID, other_run_id: uuid.UUID) -> dict:
    for rid in (base_run_id, other_run_id):
        if db.get(NomenclatureRun, rid) is None:
            raise AppError("RUN_NOT_FOUND", "Run de nomenclature introuvable.", status_code=404, detail={"run_id": str(rid)})
    a = [_item_dict(i) for i in db.scalars(select(NomenclatureItem).where(NomenclatureItem.run_id == base_run_id))]
    b = [_item_dict(i) for i in db.scalars(select(NomenclatureItem).where(NomenclatureItem.run_id == other_run_id))]
    return nomdiff.compare_runs(a, b)


@router.post("/compare", response_model=NomenclatureCompareOut)
def compare_route(payload: NomenclatureCompareIn, db: Session = Depends(get_db)) -> NomenclatureCompareOut:
    diff = _load_compare(db, payload.base_run_id, payload.other_run_id)
    return NomenclatureCompareOut(
        base_run_id=payload.base_run_id,
        other_run_id=payload.other_run_id,
        summary=nomdiff.summarize(diff),
        **diff,
    )


@router.get("/compare/export.csv")
def compare_export_csv(
    base_run_id: uuid.UUID = Query(...),
    other_run_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    diff = _load_compare(db, base_run_id, other_run_id)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    # Seul l'OLD PN est utile en comparaison (NEW PN / revisions restent dans
    # l'analyse de nomenclature pour l'etape de remplacement).
    w.writerow(["type", "sin", "old_pn", "designation"])
    for e in diff["added_sin"]:
        w.writerow(["ajoute", e["sin"], e["pn"], e["designation"]])
    for e in diff["removed_sin"]:
        w.writerow(["supprime", e["sin"], e["pn"], e["designation"]])
    for e in diff["changed_pn"]:
        w.writerow(["modifie", e["sin"], e["old_pn"], e["designation"]])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=nomenclature_diff_{str(base_run_id)[:8]}.csv"},
    )


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
    mono_body: bool | None = Query(default=None),
    replaced: bool | None = Query(default=None),
    has_color: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[NomenclatureItemOut]:
    if db.get(NomenclatureRun, run_id) is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404)
    stmt = select(NomenclatureItem).where(NomenclatureItem.run_id == run_id)
    if to_treat is not None:
        stmt = stmt.where(NomenclatureItem.to_treat == to_treat)
    if mono_color is not None:
        stmt = stmt.where(NomenclatureItem.mono_color == mono_color)
    if mono_body is not None:
        stmt = stmt.where(NomenclatureItem.mono_body == mono_body)
    if replaced is not None:
        stmt = stmt.where(NomenclatureItem.replaced == replaced)
    if has_color is not None:
        # "a une couleur" = un triplet RGB non nul est renseigne.
        colored = (
            (NomenclatureItem.color_r != 0)
            | (NomenclatureItem.color_g != 0)
            | (NomenclatureItem.color_b != 0)
        )
        stmt = stmt.where(colored if has_color else ~colored)
    return list(db.scalars(stmt.order_by(NomenclatureItem.source_row)))


@router.get("/{run_id}/export.csv")
def export_csv(
    run_id: uuid.UUID,
    to_treat: bool | None = Query(default=None),
    replaced: bool | None = Query(default=None),
    mono_body: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if db.get(NomenclatureRun, run_id) is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404)
    stmt = select(NomenclatureItem).where(NomenclatureItem.run_id == run_id)
    if to_treat is not None:
        stmt = stmt.where(NomenclatureItem.to_treat == to_treat)
    if replaced is not None:
        stmt = stmt.where(NomenclatureItem.replaced == replaced)
    if mono_body is not None:
        stmt = stmt.where(NomenclatureItem.mono_body == mono_body)
    rows = list(db.scalars(stmt.order_by(NomenclatureItem.source_row)))

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        [
            "catpart", "designation", "sin", "version", "a_traiter", "replaced",
            "old_pn", "new_pn", "old_rev", "new_rev", "color_ref", "materials",
            "slot_1", "slot_2", "slot_3", "mono_body",
            "mono_color", "r", "g", "b",
        ]
    )
    for r in rows:
        w.writerow(
            [
                r.catpart, r.designation, r.sin, r.version, r.to_treat_value, int(r.replaced),
                r.old_pn, r.new_pn, r.old_rev, r.new_rev, r.color_ref, r.materials,
                r.slot_1, r.slot_2, r.slot_3, int(r.mono_body),
                int(r.mono_color), r.color_r, r.color_g, r.color_b,
            ]
        )
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
