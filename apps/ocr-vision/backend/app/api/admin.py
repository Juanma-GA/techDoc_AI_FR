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

from app.db.models import AppConfig
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut


log = logging.getLogger("ocr-vision.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    """Compteurs sommaires pour l'onglet Donnees.

    TODO POC : remplacer par des `db.scalar(select(func.count(Modele.id)))`
    sur tes propres tables.
    """
    _ = db.scalar(select(func.count(AppConfig.key)))  # noop, exemple
    return AdminStatsOut()


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    """Reset complet sauf `app_config` (preserve la cle Mistral).

    TODO POC : etendre pour purger les tables specifiques du POC.
    """
    deleted: dict[str, int] = {}
    log.info("admin reset all (template stub)")
    return AdminResetOut(scope="all", deleted=deleted)
