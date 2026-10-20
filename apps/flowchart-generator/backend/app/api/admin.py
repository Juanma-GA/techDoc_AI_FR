"""Routes /api/v1/admin - stats globales + operations de reset.

La cle Mistral (table app_config) est preservee par convention.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Flow
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut

log = logging.getLogger("flowchart_generator.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    flows = nodes = edges = 0
    for raw in db.scalars(select(Flow.graph_json)):
        flows += 1
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes += len(data.get("nodes", []))
        edges += len(data.get("edges", []))
    return AdminStatsOut(flows=flows, nodes=nodes, edges=edges)


def _purge_flows(db: Session) -> int:
    count = db.execute(delete(Flow)).rowcount or 0
    db.commit()
    return count


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    """Reset complet sauf `app_config` (preserve la cle Mistral)."""
    deleted = {"flows": _purge_flows(db)}
    log.info("admin reset all", extra={"deleted": deleted})
    return AdminResetOut(scope="all", deleted=deleted)


@router.post("/reset/flows", response_model=AdminResetOut)
def reset_flows(db: Session = Depends(get_db)) -> AdminResetOut:
    deleted = {"flows": _purge_flows(db)}
    log.info("admin reset flows", extra={"deleted": deleted})
    return AdminResetOut(scope="flows", deleted=deleted)
