"""Routes for the persisted migration form input mapping."""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core import migration_inputs
from app.core.errors import AppError
from app.db.session import get_db

router = APIRouter(prefix="/migration-inputs", tags=["migration"])


@router.get("")
def read_mapping(db: Session = Depends(get_db)) -> dict:
    return migration_inputs.public(db)


@router.get("/{kind}")
def download_saved_input(kind: str, db: Session = Depends(get_db)) -> FileResponse:
    saved = migration_inputs.saved_file(db, kind)
    if saved is None:
        raise AppError("SAVED_INPUT_NOT_FOUND", "Fichier sauvegarde introuvable.", 404)
    path, filename = saved
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=filename)
