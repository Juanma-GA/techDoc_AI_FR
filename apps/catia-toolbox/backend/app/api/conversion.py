"""Routes /api/v1 - plan de conversion CATIA 3D -> Composer (dry-run)."""

from __future__ import annotations

import json
import os
import subprocess
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import load_parsed_nodes
from app.core import composer_converter, composer_license, conversion_planner
from app.core.errors import AppError
from app.db.models import ConversionItem, ConversionRun, StructureImport
from app.db.session import get_db
from app.schemas import (
    ComposerConverterStatusOut,
    ConversionBulkStatusIn,
    ConversionExecIn,
    ConversionExecOut,
    ConversionIn,
    ConversionItemOut,
    ConversionItemStatusIn,
    ConversionRunOut,
)

# Timeout d'execution du script de conversion (secondes).
_EXEC_TIMEOUT = 900


router = APIRouter(tags=["conversion"])


@router.get("/conversion/composer-status", response_model=ComposerConverterStatusOut)
def composer_status(db: Session = Depends(get_db)) -> ComposerConverterStatusOut:
    return ComposerConverterStatusOut(**composer_converter.get_status(db).__dict__)


@router.post("/imports/{import_id}/conversion", response_model=ConversionRunOut)
def create_conversion(import_id: uuid.UUID, body: ConversionIn, db: Session = Depends(get_db)) -> ConversionRun:
    imp = db.get(StructureImport, import_id)
    if imp is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})
    nodes, _ = load_parsed_nodes(db, import_id)
    # Dossier de sortie : celui fourni, sinon auto '<NomDossierInput>_Converti'.
    target_dir = body.target_dir.strip() or conversion_planner.output_dir_name(imp.root_label or imp.source_ref)
    items = conversion_planner.plan(nodes, target_dir=target_dir, target_ext=body.target_ext, flat=True)
    summary = conversion_planner.summarize(items)
    summary["output_dir"] = target_dir
    summary["selected"] = sum(1 for it in items if it.get("status") == "accepted")

    run = ConversionRun(
        import_id=import_id,
        config_json=json.dumps({**body.model_dump(), "target_dir": target_dir}, ensure_ascii=False),
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
                status=it.get("status", "accepted"),
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


@router.patch("/conversions/{run_id}/items/{item_id}", response_model=ConversionItemOut)
def set_item_status(
    run_id: uuid.UUID, item_id: uuid.UUID, body: ConversionItemStatusIn, db: Session = Depends(get_db)
) -> ConversionItem:
    """Selection / deselection manuelle d'un fichier a convertir."""
    item = db.get(ConversionItem, item_id)
    if item is None or item.run_id != run_id:
        raise AppError("ITEM_NOT_FOUND", "Item de conversion introuvable.", status_code=404, detail={"id": str(item_id)})
    item.status = body.status
    db.commit()
    db.refresh(item)
    return item


@router.post("/conversions/{run_id}/items/bulk-status", response_model=list[ConversionItemOut])
def bulk_item_status(
    run_id: uuid.UUID, body: ConversionBulkStatusIn, db: Session = Depends(get_db)
) -> list[ConversionItem]:
    if db.get(ConversionRun, run_id) is None:
        raise AppError("CONVERSION_NOT_FOUND", "Conversion introuvable.", status_code=404, detail={"id": str(run_id)})
    rows = list(
        db.scalars(
            select(ConversionItem).where(
                ConversionItem.run_id == run_id, ConversionItem.id.in_(body.item_ids)
            )
        )
    )
    for it in rows:
        it.status = body.status
    db.commit()
    return list(
        db.scalars(select(ConversionItem).where(ConversionItem.run_id == run_id).order_by(ConversionItem.source_path))
    )


@router.post("/conversions/{run_id}/execute", response_model=ConversionExecOut)
def execute_conversion(run_id: uuid.UUID, body: ConversionExecIn, db: Session = Depends(get_db)) -> ConversionExecOut:
    """Execute le script de conversion en local (subprocess).

    Non destructif : le script cree de nouveaux fichiers dans le dossier de
    sortie et ne supprime jamais les sources. `dry_run=True` n'appelle pas
    Composer (affiche seulement le plan). L'execution reelle exige `confirm`.
    """
    run = db.get(ConversionRun, run_id)
    if run is None:
        raise AppError("CONVERSION_NOT_FOUND", "Conversion introuvable.", status_code=404, detail={"id": str(run_id)})
    if not body.dry_run and not body.confirm:
        raise AppError("EXEC_CONFIRM_REQUIRED", "Confirmation requise pour l'execution reelle.", status_code=400)

    imp = db.get(StructureImport, run.import_id)
    if imp is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404)
    # Les chemins du plan sont relatifs a la racine locale conservee par les
    # imports de dossier et de selection.
    base = imp.source_ref if imp.source_mode in {"folder", "selection"} else ""
    if not body.dry_run and (not base or not os.path.isdir(base)):
        raise AppError(
            "EXEC_SOURCE_NOT_ON_DISK",
            "Execution reelle : utilisez un dossier local ou une selection "
            "sous la racine configuree (un .zip doit d'abord etre extrait).",
            status_code=400,
        )

    accepted_items = [item for item in run.items if item.status != "rejected"]
    if not accepted_items:
        raise AppError("EXEC_EMPTY_PLAN", "Aucun fichier selectionne pour la conversion.", status_code=400)

    env = dict(os.environ)
    license_server = composer_license.get_license_server(db)
    if license_server:
        env["COMPOSER_LICENSE_SERVER"] = license_server
        for variable in ("LM_LICENSE_FILE", "DSLICSRV", "DS_LICENSE_SERVER", "LSERVRC"):
            env.setdefault(variable, license_server)

    status = composer_converter.get_status(db)
    if not body.dry_run and not status.available:
        raise AppError("COMPOSER_NOT_READY", status.message, status_code=409)

    try:
        result = composer_converter.execute_plan(
            accepted_items,
            base=base,
            status=status,
            dry_run=body.dry_run,
            env=env,
            timeout=_EXEC_TIMEOUT,
        )
    except subprocess.TimeoutExpired as e:
        raise AppError("EXEC_TIMEOUT", f"Execution interrompue (> {_EXEC_TIMEOUT}s).", status_code=504) from e

    return ConversionExecOut(
        dry_run=body.dry_run,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        base=base,
        converted=result.converted,
        failed=result.failed,
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
    content = conversion_planner.to_pyscript(run.items, license_server=composer_license.get_license_server(db))
    return Response(
        content=content,
        media_type="text/x-python; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=conversion_composer_{str(run_id)[:8]}.py"},
    )
