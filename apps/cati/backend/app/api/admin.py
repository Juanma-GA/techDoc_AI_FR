"""Routes /api/v1/admin - stats globales + reset.

Compte les documents et items CATI. La cle Mistral (table app_config) est
preservee par convention lors d'un reset.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import CatiDocument, CatiItem
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut

log = logging.getLogger("cati.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    documents = db.scalar(select(func.count(CatiDocument.id))) or 0
    items = db.scalar(select(func.count(CatiItem.id))) or 0
    total_size = db.scalar(select(func.coalesce(func.sum(CatiDocument.size), 0))) or 0
    return AdminStatsOut(documents=int(documents), items=int(items), total_size_bytes=int(total_size))


def _purge_documents(db: Session) -> dict[str, int]:
    n_items = db.scalar(select(func.count(CatiItem.id))) or 0
    n_docs = db.scalar(select(func.count(CatiDocument.id))) or 0
    db.query(CatiItem).delete()
    db.query(CatiDocument).delete()
    db.commit()
    # Nettoyage disque best-effort.
    docs_dir = Path(settings.storage_dir) / "documents"
    if docs_dir.is_dir():
        shutil.rmtree(docs_dir, ignore_errors=True)
    return {"documents": int(n_docs), "items": int(n_items)}


@router.post("/reset/documents", response_model=AdminResetOut)
def reset_documents(db: Session = Depends(get_db)) -> AdminResetOut:
    deleted = _purge_documents(db)
    log.info("admin reset documents: %s", deleted)
    return AdminResetOut(scope="documents", deleted=deleted)


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    """Reset complet sauf `app_config` (preserve la cle Mistral)."""
    deleted = _purge_documents(db)
    log.info("admin reset all: %s", deleted)
    return AdminResetOut(scope="all", deleted=deleted)
