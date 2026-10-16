"""Workspace statistics and scoped deletion, preserving application settings."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.workspace import PRESET_ID
from app.db.models import ExcelPreset, FileAsset, ImageHistory
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut
from app.services.workspace_storage import purge_assets

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    return AdminStatsOut(
        documents=db.scalar(select(func.count(ExcelPreset.id))) or 0,
        sessions=db.scalar(select(func.count(ImageHistory.id))) or 0,
        messages=db.scalar(select(func.sum(ImageHistory.operation_count))) or 0,
        total_size_bytes=(
            (db.scalar(select(func.sum(func.length(ImageHistory.state)))) or 0)
            + (db.scalar(select(func.sum(func.length(ExcelPreset.state)))) or 0)
            + (db.scalar(select(func.sum(FileAsset.size_bytes))) or 0)
        ),
    )


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    """Delete business workspaces while preserving application settings."""
    deleted = {
        "history": db.scalar(select(func.count(ImageHistory.id))) or 0,
        "excel_presets": db.scalar(select(func.count(ExcelPreset.id))) or 0,
    }
    db.execute(delete(ImageHistory))
    db.execute(delete(ExcelPreset))
    db.commit()
    for owner in db.scalars(select(FileAsset.owner_id).distinct()).all():
        purge_assets(db, owner)
    log.info("admin_reset_all", scope="all", deleted=deleted)
    return AdminResetOut(scope="all", deleted=deleted)


@router.post("/reset/history", response_model=AdminResetOut)
def reset_history(db: Session = Depends(get_db)) -> AdminResetOut:
    count = db.scalar(select(func.count(ImageHistory.id))) or 0
    db.execute(delete(ImageHistory))
    db.commit()
    for owner in db.scalars(
        select(FileAsset.owner_id).where(FileAsset.owner_id != PRESET_ID).distinct()
    ).all():
        purge_assets(db, owner)
    log.info("admin_reset_history", scope="history", deleted={"history": count})
    return AdminResetOut(scope="history", deleted={"history": count})
