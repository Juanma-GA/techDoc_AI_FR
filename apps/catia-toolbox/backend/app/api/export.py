"""Routes export - plan CSV + script relisable (.bat / .sh), dry-run only.

Le backend ne deplace JAMAIS de fichier : il sert un PLAN (CSV) et un SCRIPT
que l'utilisateur relit puis execute lui-meme. Aucune commande destructrice.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import onedrive, plan_export
from app.core.errors import AppError
from app.core.security import safe_filename, safe_under_root
from app.db.models import OptimizationRun, Suggestion
from app.db.session import get_db
from app.schemas import ExportSaveIn, ExportSaveOut


router = APIRouter(tags=["export"])


def _suggestions_for(db: Session, run_id: uuid.UUID, status: Optional[str]) -> list[Suggestion]:
    if db.get(OptimizationRun, run_id) is None:
        raise AppError("RUN_NOT_FOUND", "Run introuvable.", status_code=404, detail={"id": str(run_id)})
    stmt = select(Suggestion).where(Suggestion.run_id == run_id)
    if status and status != "all":
        stmt = stmt.where(Suggestion.status == status)
    return list(db.scalars(stmt.order_by(Suggestion.created_at)))


@router.get("/runs/{run_id}/export.csv")
def export_csv(
    run_id: uuid.UUID,
    status: str = Query(default="accepted"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = _suggestions_for(db, run_id, status)
    content = plan_export.to_csv(rows)
    filename = f"plan_{str(run_id)[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/runs/{run_id}/export.script")
def export_script(
    run_id: uuid.UUID,
    os: str = Query(default="bat"),
    status: str = Query(default="accepted"),
    db: Session = Depends(get_db),
) -> Response:
    if os not in ("bat", "sh"):
        raise AppError("SCRIPT_OS_INVALID", "Parametre os attendu : bat ou sh.", status_code=400, detail={"os": os})
    rows = _suggestions_for(db, run_id, status)
    content = plan_export.to_bat(rows) if os == "bat" else plan_export.to_sh(rows)
    ext = "bat" if os == "bat" else "sh"
    filename = f"plan_{str(run_id)[:8]}.{ext}"
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


_EXT_FOR_KIND = {"csv": ".csv", "bat": ".bat", "sh": ".sh"}


@router.post("/runs/{run_id}/export/save", response_model=ExportSaveOut)
def export_save(
    run_id: uuid.UUID,
    payload: ExportSaveIn,
    db: Session = Depends(get_db),
) -> ExportSaveOut:
    """Ecrit le livrable genere (CSV / script dry-run) dans le dossier OneDrive
    de sortie configure.

    SEUL point d'ecriture du backend. Ecrit uniquement des livrables generes
    (jamais une piece CATIA), confine sous la racine output (anti path-traversal),
    nom de fichier assaini. Voir README ## Ecarts.
    """
    if payload.kind not in _EXT_FOR_KIND:
        raise AppError(
            "EXPORT_KIND_INVALID",
            "kind attendu : csv, bat ou sh.",
            status_code=400,
            detail={"kind": payload.kind},
        )

    rows = _suggestions_for(db, run_id, payload.status)
    if payload.kind == "csv":
        content = plan_export.to_csv(rows)
    elif payload.kind == "bat":
        content = plan_export.to_bat(rows)
    else:
        content = plan_export.to_sh(rows)

    output_root = onedrive.root_for_scope(db, "output")
    name = safe_filename(payload.filename)
    if not name.lower().endswith(_EXT_FOR_KIND[payload.kind]):
        name = f"{name}{_EXT_FOR_KIND[payload.kind]}"

    dest = safe_under_root(output_root, name)  # leve si output non configure / hors racine
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    dest.write_bytes(data)
    return ExportSaveOut(path=str(dest), bytes_written=len(data))
