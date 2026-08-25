"""Routes /api/v1/admin - stats globales + operations de reset.

Compte les BRDPs par statut de validation. Le reset "all" preserve
`app_config` (cle Mistral) et `project_config` par convention.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Brdp, Note
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut


log = logging.getLogger("brdp_manager.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    total = db.scalar(select(func.count(Brdp.id))) or 0
    validated = db.scalar(select(func.count(Brdp.id)).where(Brdp.validation == "Validated")) or 0
    refused = db.scalar(select(func.count(Brdp.id)).where(Brdp.validation == "Refused")) or 0
    pending = db.scalar(select(func.count(Brdp.id)).where(Brdp.validation == "Pending")) or 0
    return AdminStatsOut(total=total, validated=validated, refused=refused, pending=pending)


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    """Supprime tous les BRDPs et notes. Preserve `app_config` + `project_config`."""
    brdps_count = db.query(Brdp).delete()
    notes_count = db.query(Note).delete()
    db.commit()
    log.info("admin reset all: brdps=%s notes=%s", brdps_count, notes_count)
    return AdminResetOut(scope="all", deleted={"brdps": brdps_count, "notes": notes_count})
