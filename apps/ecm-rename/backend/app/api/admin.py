"""Routes /api/v1/admin - stats globales + operations de reset."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.schemas import AdminResetOut, AdminStatsOut

log = logging.getLogger("ecm_rename.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats() -> AdminStatsOut:
    """Compteurs sommaires pour l'onglet Donnees.

    TODO POC : remplacer par des `db.scalar(select(func.count(Modele.id)))`
    sur tes propres tables.
    """
    return AdminStatsOut()


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all() -> AdminResetOut:
    """Reset no-op : aucune donnée métier n'est persistée par l'application.

    TODO POC : etendre pour purger les tables specifiques du POC.
    """
    deleted: dict[str, int] = {}
    log.info("admin reset all")
    return AdminResetOut(scope="all", deleted=deleted)
