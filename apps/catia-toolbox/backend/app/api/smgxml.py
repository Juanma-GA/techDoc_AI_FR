"""Routes /api/v1/smgxml : renommage du SMGXML.

Dry-run par defaut (`apply=false` : on calcule les changements sans ecrire).
Avec `apply=true`, le SMGXML est modifie en conservant une copie `.bak`.
Chemins confines sous la racine du scope (anti path-traversal).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import onedrive
from app.core import smgxml_batch
from app.core import smgxml_rename as smgxml_engine
from app.core.errors import AppError
from app.core.security import safe_under_root
from app.db.models import NomenclatureItem, NomenclatureRun, SmgxmlChange, SmgxmlRun
from app.db.session import get_db
from app.schemas import (
    SmgxmlBatchOut,
    SmgxmlBatchRenameIn,
    SmgxmlChangeOut,
    SmgxmlRenameIn,
    SmgxmlRunOut,
)


log = logging.getLogger("catia_toolbox.smgxml")

router = APIRouter(prefix="/smgxml", tags=["smgxml"])


def _run_out(run: SmgxmlRun) -> SmgxmlRunOut:
    return SmgxmlRunOut(
        id=run.id,
        source_ref=run.source_ref,
        operation=run.operation,
        status=run.status,
        applied=run.applied,
        backup_path=run.backup_path,
        output_path=run.output_path,
        summary=json.loads(run.summary or "{}"),
        created_at=run.created_at,
    )


def _resolve(db: Session, scope: str, path: str):
    if scope not in ("input", "output"):
        raise AppError("SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)
    root = onedrive.root_for_scope(db, scope)
    target = safe_under_root(root, path)
    if not target.is_file():
        raise AppError("SMGXML_NOT_FOUND", "SMGXML introuvable.", status_code=404, detail={"path": str(target)})
    return target


def _persist(db: Session, *, source_ref: str, operation: str, result: dict) -> SmgxmlRun:
    run = SmgxmlRun(
        source_ref=source_ref,
        operation=operation,
        status="applied" if result["applied"] else "planned",
        applied=result["applied"],
        backup_path=result["backup_path"],
        output_path=result["output_path"],
        config_json="{}",
        summary=json.dumps(result["summary"], ensure_ascii=False),
    )
    db.add(run)
    db.flush()
    for ch in result["changes"]:
        db.add(SmgxmlChange(run_id=run.id, **ch))
    db.commit()
    db.refresh(run)
    return run


def _resolve_dir(db: Session, scope: str, path: str, code: str):
    if scope not in ("input", "output"):
        raise AppError("SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)
    root = onedrive.root_for_scope(db, scope)
    target = safe_under_root(root, path)
    if not target.is_dir():
        raise AppError(code, "Dossier introuvable.", status_code=404, detail={"path": str(target)})
    return target


@router.post("/batch-rename", response_model=SmgxmlBatchOut)
def batch_rename(payload: SmgxmlBatchRenameIn, db: Session = Depends(get_db)) -> SmgxmlBatchOut:
    """Renommage en masse des pieces remplacees d'une nomenclature (etape 4).

    Dry-run par defaut ; `apply=true` archive les OLD, copie les NEW et edite les
    assemblages (+ .bak). Voir core/smgxml_batch.py pour le detail du process."""
    composer = _resolve_dir(db, payload.scope, payload.composer_root, "COMPOSER_ROOT_NOT_FOUND")
    converted = _resolve_dir(db, payload.scope, payload.converted_root, "CONVERTED_ROOT_NOT_FOUND")

    run = db.get(NomenclatureRun, payload.nomenclature_run_id)
    if run is None:
        raise AppError("RUN_NOT_FOUND", "Nomenclature introuvable.", status_code=404)
    run_items = db.scalars(
        select(NomenclatureItem).where(NomenclatureItem.run_id == payload.nomenclature_run_id)
    )
    items = [
        {"sin": it.sin, "old_pn": it.old_pn, "new_pn": it.new_pn, "designation": it.designation}
        for it in run_items
        if (it.old_pn or "").strip() and (it.new_pn or "").strip()
        and (it.old_pn or "").strip() != (it.new_pn or "").strip()
    ]

    archive_ts = "ARCHIVE_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    result = smgxml_batch.plan_batch_rename(
        str(composer), str(converted), items, apply=payload.apply, archive_ts=archive_ts
    )
    log.info(
        "batch-rename run %s : %d items, %d ok, applied=%s",
        payload.nomenclature_run_id, result["summary"]["total"], result["summary"]["ok"], payload.apply,
    )
    return SmgxmlBatchOut(**result)


@router.post("/rename", response_model=SmgxmlRunOut)
def rename(payload: SmgxmlRenameIn, db: Session = Depends(get_db)) -> SmgxmlRunOut:
    target = _resolve(db, payload.scope, payload.path)
    rename_map = {p.old: p.new for p in payload.mapping}
    result = smgxml_engine.rename(str(target), rename_map, apply=payload.apply)
    run = _persist(db, source_ref=str(target), operation="rename", result=result)
    log.info("smgxml rename %s : %d changements (applied=%s)", run.id, result["summary"]["changes"], result["applied"])
    return _run_out(run)


@router.get("", response_model=list[SmgxmlRunOut])
def list_runs(db: Session = Depends(get_db)) -> list[SmgxmlRunOut]:
    rows = db.scalars(select(SmgxmlRun).order_by(SmgxmlRun.created_at.desc()))
    return [_run_out(r) for r in rows]


@router.get("/{run_id}", response_model=SmgxmlRunOut)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> SmgxmlRunOut:
    run = db.get(SmgxmlRun, run_id)
    if run is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404)
    return _run_out(run)


@router.get("/{run_id}/changes", response_model=list[SmgxmlChangeOut])
def list_changes(run_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SmgxmlChangeOut]:
    if db.get(SmgxmlRun, run_id) is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404)
    return list(db.scalars(select(SmgxmlChange).where(SmgxmlChange.run_id == run_id)))
