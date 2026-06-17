"""Routes /api/v1/qc - Etape 5 : checklist Controle Qualite (facon revue Word).

Une checklist = des items cochables (pending / ok / ko / na) avec commentaire.
Modele simple et interactif : creer une checklist (template par defaut ou items
fournis), mettre a jour chaque item, exporter un rapport CSV.
"""

from __future__ import annotations

import csv
import io
import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import QcChecklist, QcItem
from app.db.session import get_db
from app.schemas import QcChecklistCreateIn, QcChecklistOut, QcItemOut, QcItemUpdateIn
from fastapi.responses import StreamingResponse


log = logging.getLogger("catia_toolbox.qc")

router = APIRouter(prefix="/qc", tags=["qc"])

_VALID_STATUS = {"pending", "ok", "ko", "na"}

# Checklist par defaut "verification des pieces dans l'assemblage" (etape 5).
_TEMPLATE_ASSEMBLY: list[tuple[str, str]] = [
    ("Arborescence", "L'arborescence CATComposer est conforme au standard moteur."),
    ("Arborescence", "Aucune piece orpheline / non rattachee dans l'assemblage."),
    ("Remplacement", "Toutes les pieces Uxxx n-1 ont ete remplacees par Uxxx n."),
    ("Remplacement", "Les references (liens) pointent vers les nouvelles pieces."),
    ("Couleur", "Les pieces mono-couleur portent la bonne couleur (SIN)."),
    ("Couleur", "Aucune piece sans materiau / couleur attendue."),
    ("Fichiers", "Les fichiers COMP PART correspondent aux pieces de l'assemblage."),
    ("Fichiers", "Aucun doublon de piece dans le dossier de production."),
    ("Integration", "Le SMGXML s'ouvre sans erreur dans l'ecosysteme moteur."),
    ("Integration", "Le merge multi-environnements est coherent (pas de conflit)."),
]


def _summary(items: list[QcItem]) -> dict:
    counts = {"pending": 0, "ok": 0, "ko": 0, "na": 0}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1
    counts["total"] = len(items)
    counts["done"] = counts["ok"] + counts["ko"] + counts["na"]
    return counts


def _out(db: Session, checklist: QcChecklist) -> QcChecklistOut:
    items = list(db.scalars(select(QcItem).where(QcItem.checklist_id == checklist.id).order_by(QcItem.position)))
    return QcChecklistOut(
        id=checklist.id,
        title=checklist.title,
        status=checklist.status,
        created_at=checklist.created_at,
        items=[QcItemOut.model_validate(it) for it in items],
        summary=_summary(items),
    )


@router.post("/checklists", response_model=QcChecklistOut)
def create_checklist(payload: QcChecklistCreateIn, db: Session = Depends(get_db)) -> QcChecklistOut:
    checklist = QcChecklist(title=payload.title[:300] or "Controle qualite", status="open")
    db.add(checklist)
    db.flush()

    if payload.items:
        rows = [(it.label, it.category) for it in payload.items]
    elif payload.template == "assembly" or not payload.items:
        rows = [(label, cat) for cat, label in _TEMPLATE_ASSEMBLY]
    else:
        rows = []
    for pos, (label, category) in enumerate(rows):
        db.add(QcItem(checklist_id=checklist.id, label=label, category=category, position=pos))
    db.commit()
    db.refresh(checklist)
    log.info("qc checklist %s : %d items", checklist.id, len(rows))
    return _out(db, checklist)


@router.get("/checklists", response_model=list[QcChecklistOut])
def list_checklists(db: Session = Depends(get_db)) -> list[QcChecklistOut]:
    rows = db.scalars(select(QcChecklist).order_by(QcChecklist.created_at.desc()))
    return [_out(db, c) for c in rows]


@router.get("/checklists/{checklist_id}", response_model=QcChecklistOut)
def get_checklist(checklist_id: uuid.UUID, db: Session = Depends(get_db)) -> QcChecklistOut:
    checklist = db.get(QcChecklist, checklist_id)
    if checklist is None:
        raise AppError("CHECKLIST_NOT_FOUND", "Checklist introuvable.", status_code=404)
    return _out(db, checklist)


@router.patch("/items/{item_id}", response_model=QcItemOut)
def update_item(item_id: uuid.UUID, payload: QcItemUpdateIn, db: Session = Depends(get_db)) -> QcItemOut:
    item = db.get(QcItem, item_id)
    if item is None:
        raise AppError("ITEM_NOT_FOUND", "Item introuvable.", status_code=404)
    if payload.status is not None:
        if payload.status not in _VALID_STATUS:
            raise AppError("STATUS_INVALID", f"status attendu : {sorted(_VALID_STATUS)}.", status_code=400)
        item.status = payload.status
    if payload.comment is not None:
        item.comment = payload.comment
    db.commit()
    db.refresh(item)
    return QcItemOut.model_validate(item)


@router.get("/checklists/{checklist_id}/export.csv")
def export_csv(checklist_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    checklist = db.get(QcChecklist, checklist_id)
    if checklist is None:
        raise AppError("CHECKLIST_NOT_FOUND", "Checklist introuvable.", status_code=404)
    items = list(db.scalars(select(QcItem).where(QcItem.checklist_id == checklist_id).order_by(QcItem.position)))
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["categorie", "verification", "statut", "commentaire"])
    for it in items:
        w.writerow([it.category, it.label, it.status, it.comment])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=qc_{str(checklist_id)[:8]}.csv"},
    )


@router.delete("/checklists/{checklist_id}", status_code=204)
def delete_checklist(checklist_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    checklist = db.get(QcChecklist, checklist_id)
    if checklist is None:
        raise AppError("CHECKLIST_NOT_FOUND", "Checklist introuvable.", status_code=404)
    db.delete(checklist)
    db.commit()
