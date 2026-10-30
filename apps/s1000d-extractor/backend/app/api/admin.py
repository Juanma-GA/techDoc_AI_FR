"""Routes /api/v1/admin - stats globales + reset.

Le mode de fonctionnement (app_config) et les profils BREX sont preserves par les
resets (le BREX est une config projet, pas de la donnee jetable).
"""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.fs import remove_files
from app.db.models import BrexProfile, DmDocumentLink, DmVersion, Document
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut

log = structlog.get_logger("s1000d_extractor.admin")

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
        except OSError as exc:
            log.warning("document_size_failed", path=path, error_type=type(exc).__name__, exc_info=True)
    return AdminStatsOut(
        documents=docs, extracted=extracted, brex_profiles=brex, total_size_bytes=total_size
    )


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(
    db: Session = Depends(get_db),
    confirm_token: str = Query("", min_length=10),
) -> AdminResetOut:
    """
    Reset all documents. Requires a confirm_token from the frontend (double-click pattern).
    Complies with HR9: never delete persistent user data without explicit confirmation.

    Query param: ?confirm_token=<random_value_>=10_chars>
    Frontend enforces double-click: send with a generated token on second click.
    """
    if not confirm_token:
        raise AppError(
            "DELETE_NOT_CONFIRMED",
            "Deletion requires confirmation. Use the double-click pattern in UI.",
            422,
        )
    return _reset_documents(db, scope="all")


@router.post("/reset/documents", response_model=AdminResetOut)
def reset_documents(
    db: Session = Depends(get_db),
    confirm_token: str = Query("", min_length=10),
) -> AdminResetOut:
    """
    Reset documents only (preserve BREX profiles).
    Query param: ?confirm_token=<random_value_>=10_chars>
    """
    if not confirm_token:
        raise AppError(
            "DELETE_NOT_CONFIRMED",
            "Deletion requires confirmation. Use the double-click pattern in UI.",
            422,
        )
    return _reset_documents(db, scope="documents")


def _reset_documents(db: Session, *, scope: str) -> AdminResetOut:
    """Purge documents + fichiers (PDF/DOCX/XML). Preserve app_config + BREX."""
    from app.core.wizard import images_dir

    docs = db.scalars(select(Document)).all()
    paths: list[Path] = []
    directories: list[Path] = []
    for d in docs:
        for p in (
            d.storage_path,
            d.pdf_cut_path,
            d.xml_path,
            d.dmrl_path,
            d.dm_header_path,
            d.cir_path,
            d.brex_rules_path,
        ):
            if p:
                paths.append(Path(p))
        directories.append(images_dir(d.id, root=Path(d.storage_path).parent))
    count = len(docs)
    db.query(DmDocumentLink).delete()
    db.query(DmVersion).delete()
    db.query(Document).delete()
    db.commit()
    remove_files(paths, directories=directories)
    log.info("admin_reset", scope=scope, documents=count)
    return AdminResetOut(scope=scope, deleted={"documents": count})
