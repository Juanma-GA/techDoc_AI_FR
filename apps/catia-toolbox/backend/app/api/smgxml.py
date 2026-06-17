"""Routes /api/v1/smgxml - Etapes 3 & 4 : recolor / rename du SMGXML.

Dry-run par defaut (`apply=false` : on calcule les changements sans ecrire).
Avec `apply=true`, le SMGXML est modifie en conservant une copie `.bak`.
Chemins confines sous la racine du scope (anti path-traversal).
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import onedrive
from app.core import smgxml as smgxml_engine
from app.core.errors import AppError
from app.core.security import safe_under_root
from app.db.models import NomenclatureItem, NomenclatureRun, SmgxmlChange, SmgxmlRun
from app.db.session import get_db
from app.schemas import (
    SmgxmlActorOut,
    SmgxmlChangeOut,
    SmgxmlInspectIn,
    SmgxmlRecolorIn,
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


@router.post("/inspect", response_model=list[SmgxmlActorOut])
def inspect(payload: SmgxmlInspectIn, db: Session = Depends(get_db)) -> list[SmgxmlActorOut]:
    target = _resolve(db, payload.scope, payload.path)
    return [SmgxmlActorOut(**a) for a in smgxml_engine.parse_actors(str(target))]


@router.post("/recolor", response_model=SmgxmlRunOut)
def recolor(payload: SmgxmlRecolorIn, db: Session = Depends(get_db)) -> SmgxmlRunOut:
    target = _resolve(db, payload.scope, payload.path)
    if db.get(NomenclatureRun, payload.nomenclature_run_id) is None:
        raise AppError("RUN_NOT_FOUND", "Nomenclature introuvable.", status_code=404)
    if payload.match_by not in ("sin", "catpart"):
        raise AppError("MATCH_BY_INVALID", "match_by attendu : sin ou catpart.", status_code=400)

    mono = db.scalars(
        select(NomenclatureItem).where(
            NomenclatureItem.run_id == payload.nomenclature_run_id,
            NomenclatureItem.mono_color.is_(True),
        )
    )
    color_map: dict[str, tuple[int, int, int]] = {}
    for it in mono:
        key = (it.sin if payload.match_by == "sin" else it.catpart).strip()
        if key:
            color_map[key] = (it.color_r, it.color_g, it.color_b)
    if not color_map:
        raise AppError("NO_MONO_COLOR", "Aucune piece mono-couleur dans cette nomenclature.", status_code=400)

    result = smgxml_engine.process(str(target), "recolor", color_map=color_map, apply=payload.apply)
    run = _persist(db, source_ref=str(target), operation="recolor", result=result)
    log.info("smgxml recolor %s : %d changements (applied=%s)", run.id, result["summary"]["changes"], result["applied"])
    return _run_out(run)


@router.post("/rename", response_model=SmgxmlRunOut)
def rename(payload: SmgxmlRenameIn, db: Session = Depends(get_db)) -> SmgxmlRunOut:
    target = _resolve(db, payload.scope, payload.path)
    rename_map = {p.old: p.new for p in payload.mapping}
    result = smgxml_engine.process(str(target), "rename", rename_map=rename_map, apply=payload.apply)
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
