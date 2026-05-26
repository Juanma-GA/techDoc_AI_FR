"""Routes /api/v1/admin — stats globales + operations de reset.

Conforme au pattern partage par ftm et pdf-reviewer : un onglet "Donnees"
dans l'UI consomme ces routes pour afficher les compteurs et offrir des
boutons de reinitialisation. Mistral settings et fichiers du venv ne sont
pas touches.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Document, DocumentChunk, Message
from app.db.models import Session as SessionRow
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut


log = logging.getLogger("doc_writer.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    """Compteurs sommaires pour l'onglet Donnees."""
    doc_count = db.scalar(select(func.count(Document.id))) or 0
    chunk_count = db.scalar(select(func.count(DocumentChunk.id))) or 0
    session_count = db.scalar(select(func.count(SessionRow.id))) or 0
    message_count = db.scalar(select(func.count(Message.id))) or 0
    total_size = db.scalar(select(func.coalesce(func.sum(Document.size), 0))) or 0
    return AdminStatsOut(
        documents=doc_count,
        chunks=chunk_count,
        sessions=session_count,
        messages=message_count,
        total_size_bytes=int(total_size),
    )


def _purge_storage(subdir: str) -> int:
    """Supprime un sous-dossier de storage_dir (best effort). Retourne 0/1."""
    target = Path(settings.storage_dir) / subdir
    if target.exists() and target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
        return 1
    return 0


@router.post("/reset/documents", response_model=AdminResetOut)
def reset_documents(db: Session = Depends(get_db)) -> AdminResetOut:
    """Supprime tous les documents (chunks en cascade) + fichiers disque."""
    doc_count = db.scalar(select(func.count(Document.id))) or 0
    chunk_count = db.scalar(select(func.count(DocumentChunk.id))) or 0
    db.query(DocumentChunk).delete()
    db.query(Document).delete()
    db.commit()
    _purge_storage("documents")
    log.info("admin reset documents: %d docs, %d chunks", doc_count, chunk_count)
    return AdminResetOut(
        scope="documents",
        deleted={"documents": int(doc_count), "chunks": int(chunk_count)},
    )


@router.post("/reset/sessions", response_model=AdminResetOut)
def reset_sessions(db: Session = Depends(get_db)) -> AdminResetOut:
    """Supprime toutes les sessions + messages."""
    session_count = db.scalar(select(func.count(SessionRow.id))) or 0
    message_count = db.scalar(select(func.count(Message.id))) or 0
    db.query(Message).delete()
    db.query(SessionRow).delete()
    db.commit()
    log.info("admin reset sessions: %d sessions, %d messages", session_count, message_count)
    return AdminResetOut(
        scope="sessions",
        deleted={"sessions": int(session_count), "messages": int(message_count)},
    )


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    """Supprime tout sauf la config Mistral (table app_config preservee)."""
    counts = {
        "documents": db.scalar(select(func.count(Document.id))) or 0,
        "chunks": db.scalar(select(func.count(DocumentChunk.id))) or 0,
        "sessions": db.scalar(select(func.count(SessionRow.id))) or 0,
        "messages": db.scalar(select(func.count(Message.id))) or 0,
    }
    db.query(Message).delete()
    db.query(SessionRow).delete()
    db.query(DocumentChunk).delete()
    db.query(Document).delete()
    db.commit()
    _purge_storage("documents")
    log.info("admin reset all: %s", counts)
    return AdminResetOut(scope="all", deleted={k: int(v) for k, v in counts.items()})
