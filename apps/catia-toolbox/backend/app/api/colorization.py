"""Batch Colorization for mono-body Composer piece XML files."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import onedrive
from app.core.errors import AppError
from app.core.security import safe_under_root
from app.core.smgxml_colorization import colorize_mono_body_folder
from app.db.models import NomenclatureItem, NomenclatureRun
from app.db.session import get_db
from app.schemas import MonoBodyColorizationIn, MonoBodyColorizationOut


log = logging.getLogger("catia_toolbox.colorization")

router = APIRouter(prefix="/colorization", tags=["colorization"])


@router.post("/mono-body", response_model=MonoBodyColorizationOut)
def colorize_mono_body(
    payload: MonoBodyColorizationIn,
    db: Session = Depends(get_db),
) -> MonoBodyColorizationOut:
    if payload.scope not in ("input", "output"):
        raise AppError("SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)

    run = db.get(NomenclatureRun, payload.nomenclature_run_id)
    if run is None:
        raise AppError("RUN_NOT_FOUND", "Nomenclature introuvable.", status_code=404)

    root = onedrive.root_for_scope(db, payload.scope)
    pieces_root = safe_under_root(root, payload.pieces_root)
    profiles_root = safe_under_root(root, payload.profiles_root)
    if not pieces_root.is_dir():
        raise AppError(
            "PIECES_ROOT_NOT_FOUND",
            "Dossier des pièces introuvable.",
            status_code=404,
            detail={"path": str(pieces_root)},
        )
    if not profiles_root.is_dir():
        raise AppError(
            "PROFILES_ROOT_NOT_FOUND",
            "Dossier des profils Composer introuvable.",
            status_code=404,
            detail={"path": str(profiles_root)},
        )

    rows = db.scalars(
        select(NomenclatureItem).where(
            NomenclatureItem.run_id == payload.nomenclature_run_id,
            NomenclatureItem.mono_body.is_(True),
        )
    )
    mono_parts = [
        {"old_pn": item.old_pn, "mono_texture": item.mono_texture}
        for item in rows
    ]
    result = colorize_mono_body_folder(
        pieces_root,
        profiles_root,
        mono_parts,
        apply=payload.apply,
    )
    log.info(
        "colorisation mono-corps run %s : %d fichiers changes, applique=%s",
        payload.nomenclature_run_id,
        result["summary"]["files_changed"],
        payload.apply,
    )
    return MonoBodyColorizationOut(**result)