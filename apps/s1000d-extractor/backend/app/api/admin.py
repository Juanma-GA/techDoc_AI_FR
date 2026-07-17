"""Routes /api/v1/admin - stats globales + reset.

La cle Mistral (app_config) ET les profils BREX sont preserves par les resets
(le BREX est une config projet, pas de la donnee jetable).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import BrexProfile, Document
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut

log = logging.getLogger("s1000d_extractor.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    docs = db.scalar(select(func.count(Document.id))) or 0
    extracted = db.scalar(
        select(func.count(Document.id)).where(Document.status == "extracted")
    ) or 0
    brex = db.scalar(select(func.count(BrexProfile.id))) or 0
    total_size = 0
    for (path,) in db.execute(select(Document.storage_path)).all():
        try:
            total_size += Path(path).stat().st_size
        except OSError:
            pass
    return AdminStatsOut(
        documents=docs, extracted=extracted, brex_profiles=brex, total_size_bytes=total_size
    )


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    return _reset_documents(db, scope="all")


@router.post("/reset/documents", response_model=AdminResetOut)
def reset_documents(db: Session = Depends(get_db)) -> AdminResetOut:
    return _reset_documents(db, scope="documents")


def _reset_documents(db: Session, *, scope: str) -> AdminResetOut:
    """Purge documents + fichiers (PDF/DOCX/XML). Preserve app_config + BREX."""
    import shutil

    from app.core.wizard import images_dir

    docs = db.scalars(select(Document)).all()
    for d in docs:
        for p in (d.storage_path, d.xml_path):
            if p:
                try:
                    Path(p).unlink(missing_ok=True)
                except OSError:
                    pass
        try:
            shutil.rmtree(images_dir(d.id), ignore_errors=True)  # illustrations extraites
        except OSError:
            pass
    count = len(docs)
    db.query(Document).delete()
    db.commit()
    log.info("admin reset scope=%s documents=%d", scope, count)
    return AdminResetOut(scope=scope, deleted={"documents": count})
