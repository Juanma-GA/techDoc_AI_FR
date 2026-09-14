"""Routes /api/v1/admin — stats globales + operations de reset.

Conforme au pattern partage par corpus-agent et pdf-reviewer : un onglet "Donnees"
dans l'UI consomme ces routes pour afficher les compteurs et offrir des
boutons de reinitialisation. Mistral settings et fichiers du venv ne sont
pas touches.

F-06 (hardening 2026-09-14) : les resets etaient irreversibles, non confirmes
cote serveur (le double-clic frontend est bypassable, ex. curl direct — prouve
par DAST : reset/all a rendu 200 et tout efface sans rien envoyer) et sans
auth. Une auth reelle reste hors perimetre du standard POC local-first (meme
raisonnement que F-02) ; a la place : (1) un jeton de confirmation explicite
est desormais requis dans le corps de la requete, (2) la DB SQLite est
sauvegardee avant toute suppression, (3) les fichiers de storage sont
deplaces vers une corbeille horodatee plutot que rmtree definitivement.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.db.models import Document, DocumentChunk, Message
from app.db.models import Session as SessionRow
from app.db.session import get_db
from app.schemas import AdminResetIn, AdminResetOut, AdminStatsOut


log = logging.getLogger("doc_writer.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_confirmation(payload: AdminResetIn, scope: str) -> None:
    """F-06 : le corps de la requete doit porter `{"confirm": "<scope>"}`
    exactement. Bloque tout POST « aveugle » (curl sans payload, scan
    automatise) qui atteindrait l'endpoint sans passer par l'UI."""
    if payload.confirm != scope:
        raise AppError(
            code="CONFIRMATION_REQUIRED",
            message=f'Confirmation requise : envoyer {{"confirm": "{scope}"}}.',
            status_code=400,
            detail={"scope": scope},
        )


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _backup_sqlite_db(scope: str) -> str | None:
    """Copie best-effort de la DB SQLite avant un reset destructeur. Renvoie
    le chemin du backup, ou None si la DB n'est pas SQLite ou si la copie a
    echoue (ne bloque jamais le reset : c'est un filet de securite, pas une
    garantie transactionnelle)."""
    prefix = "sqlite:///"
    url = settings.database_url
    if not url.startswith(prefix):
        return None
    db_path = Path(url[len(prefix) :])
    if not db_path.exists():
        return None
    backup_dir = db_path.parent / "backups"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{db_path.stem}.pre-reset-{scope}.{_timestamp()}{db_path.suffix}"
        shutil.copy2(db_path, backup_path)
    except OSError as e:
        log.error("admin reset backup failed (scope=%s): %s", scope, e)
        return None
    return str(backup_path)


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
    """Deplace un sous-dossier de storage_dir vers une corbeille horodatee au
    lieu d'un rmtree definitif (F-06 : soft-delete, recuperable manuellement).
    Retourne 0/1. La corbeille (`storage/_trash/`) s'accumule au fil des
    resets ; c'est un compromis assume pour un POC local-first — la purger
    reste une operation manuelle de l'operateur."""
    target = Path(settings.storage_dir) / subdir
    if not (target.exists() and target.is_dir()):
        return 0
    trash_dir = Path(settings.storage_dir) / "_trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(target), str(trash_dir / f"{subdir}.{_timestamp()}"))
    return 1


@router.post("/reset/documents", response_model=AdminResetOut)
def reset_documents(payload: AdminResetIn, db: Session = Depends(get_db)) -> AdminResetOut:
    """Supprime tous les documents (chunks en cascade) + fichiers disque."""
    _require_confirmation(payload, "documents")
    backup_path = _backup_sqlite_db("documents")
    doc_count = db.scalar(select(func.count(Document.id))) or 0
    chunk_count = db.scalar(select(func.count(DocumentChunk.id))) or 0
    db.query(DocumentChunk).delete()
    db.query(Document).delete()
    db.commit()
    _purge_storage("documents")
    log.info("admin reset documents: %d docs, %d chunks (backup=%s)", doc_count, chunk_count, backup_path)
    return AdminResetOut(
        scope="documents",
        deleted={"documents": int(doc_count), "chunks": int(chunk_count)},
        backup_path=backup_path,
    )


@router.post("/reset/sessions", response_model=AdminResetOut)
def reset_sessions(payload: AdminResetIn, db: Session = Depends(get_db)) -> AdminResetOut:
    """Supprime toutes les sessions + messages."""
    _require_confirmation(payload, "sessions")
    backup_path = _backup_sqlite_db("sessions")
    session_count = db.scalar(select(func.count(SessionRow.id))) or 0
    message_count = db.scalar(select(func.count(Message.id))) or 0
    db.query(Message).delete()
    db.query(SessionRow).delete()
    db.commit()
    log.info(
        "admin reset sessions: %d sessions, %d messages (backup=%s)",
        session_count,
        message_count,
        backup_path,
    )
    return AdminResetOut(
        scope="sessions",
        deleted={"sessions": int(session_count), "messages": int(message_count)},
        backup_path=backup_path,
    )


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(payload: AdminResetIn, db: Session = Depends(get_db)) -> AdminResetOut:
    """Supprime tout sauf la config Mistral (table app_config preservee)."""
    _require_confirmation(payload, "all")
    backup_path = _backup_sqlite_db("all")
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
    log.info("admin reset all: %s (backup=%s)", counts, backup_path)
    return AdminResetOut(
        scope="all", deleted={k: int(v) for k, v in counts.items()}, backup_path=backup_path
    )
