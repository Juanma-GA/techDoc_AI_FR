"""Routes /api/v1/admin - stats globales + operations de reset.

Version generique : compte uniquement `AppConfig`. Chaque POC doit
remplacer le contenu de `stats()` et `reset_all()` pour ses propres tables.
La cle Mistral (table app_config) est preservee par convention.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import shutil
from pathlib import Path

from app.config import settings
from app.db.models import ExtractedImage, ExtractedRow, Project, ProjectTable, TableTemplate
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut


log = logging.getLogger("ocr-vision.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


def _count(db: Session, model: type) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    return AdminStatsOut(
        projects=_count(db, Project),
        templates=_count(db, TableTemplate),
        tables=_count(db, ProjectTable),
        rows=_count(db, ExtractedRow),
        images=_count(db, ExtractedImage),
    )


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    """Reset complet sauf `app_config` (preserve la cle Mistral)."""
    deleted = {
        "images": db.query(ExtractedImage).delete(),
        "rows": db.query(ExtractedRow).delete(),
        "tables": db.query(ProjectTable).delete(),
        "projects": db.query(Project).delete(),
        "templates": db.query(TableTemplate).delete(),
    }
    db.commit()
    # Purge des fichiers images sur disque (best-effort).
    storage = Path(settings.storage_dir)
    if storage.is_dir():
        try:
            shutil.rmtree(storage, ignore_errors=True)
        except OSError:
            pass
    log.info("admin reset all: %s", deleted)
    return AdminResetOut(scope="all", deleted={k: int(v) for k, v in deleted.items()})
