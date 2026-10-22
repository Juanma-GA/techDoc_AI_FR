"""Routes /api/v1/admin - stats globales + operations de reset.

Version generique : compte uniquement `AppConfig`. Chaque POC doit
remplacer le contenu de `stats()` et `reset_all()` pour ses propres tables.
La table app_config est preservee par convention (reglages runtime).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AppConfig
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut


log = structlog.get_logger(__name__)

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
    """Reset complet sauf `app_config` (preserve les reglages et preferences).

    TODO POC : etendre pour purger les tables specifiques du POC — garder le
    log structure `admin_reset_all` (scope + deleted) comme trace d'audit de
    cette action destructrice (RequestIdMiddleware y attache le request_id).
    """
    deleted: dict[str, int] = {}
    log.info("admin_reset_all", scope="all", deleted=deleted)
    return AdminResetOut(scope="all", deleted=deleted)
