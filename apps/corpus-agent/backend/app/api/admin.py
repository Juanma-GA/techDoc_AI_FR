"""GET /api/v1/admin/stats + POST /api/v1/admin/reset.

Outils d'administration des données : compteurs, tailles disque, reset par
scope (`analyses`, `chat`, `all`). Les paramètres Mistral et l'override
des règles métier (data/rules.json) sont préservés dans tous les scopes.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    AnalysisRun,
    Anomaly,
    ChatMessage,
    ChatSession,
    DocumentChunk,
    File,
    FileVersion,
    Project,
)
from app.db.session import get_db


router = APIRouter(prefix="/admin", tags=["admin"])


class AdminStatsOut(BaseModel):
    projects: int
    files: int
    file_versions: int
    anomalies: int
    analysis_runs: int
    chat_sessions: int
    chat_messages: int
    document_chunks: int
    storage_bytes: int
    db_bytes: int


class AdminResetIn(BaseModel):
    scope: Literal["analyses", "chat", "all"]


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]


def _dir_size(path: Path) -> int:
    if not path.is_dir():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                continue
    return total


def _sqlite_path() -> Path | None:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return Path(url.removeprefix("sqlite:///"))
    return None


@router.get("/stats", response_model=AdminStatsOut)
def get_stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    db_path = _sqlite_path()
    db_bytes = 0
    if db_path is not None:
        try:
            if db_path.is_file():
                db_bytes = db_path.stat().st_size
        except OSError:
            db_bytes = 0
    return AdminStatsOut(
        projects=db.scalar(select(func.count(Project.id))) or 0,
        files=db.scalar(select(func.count(File.id))) or 0,
        file_versions=db.scalar(select(func.count(FileVersion.id))) or 0,
        anomalies=db.scalar(select(func.count(Anomaly.id))) or 0,
        analysis_runs=db.scalar(select(func.count(AnalysisRun.id))) or 0,
        chat_sessions=db.scalar(select(func.count(ChatSession.id))) or 0,
        chat_messages=db.scalar(select(func.count(ChatMessage.id))) or 0,
        document_chunks=db.scalar(select(func.count(DocumentChunk.id))) or 0,
        storage_bytes=_dir_size(Path(settings.storage_dir)),
        db_bytes=db_bytes,
    )


def _wipe_storage_dir() -> None:
    """Vide `data/storage/` (sans supprimer le dossier lui-même)."""
    storage_dir = Path(settings.storage_dir)
    if not storage_dir.is_dir():
        return
    for child in storage_dir.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError:
            continue


@router.post("/reset", response_model=AdminResetOut)
def reset_data(body: AdminResetIn, db: Session = Depends(get_db)) -> AdminResetOut:
    """Supprime les données du scope demandé. SQLite ne propage pas les FKs
    par défaut → on supprime explicitement dans l'ordre de dépendance
    (feuilles d'abord, racines ensuite)."""
    deleted: dict[str, int] = {}

    if body.scope in ("analyses", "all"):
        deleted["anomalies"] = db.query(Anomaly).delete(synchronize_session=False)
        deleted["document_chunks"] = db.query(DocumentChunk).delete(synchronize_session=False)
        deleted["analysis_runs"] = db.query(AnalysisRun).delete(synchronize_session=False)

    if body.scope in ("chat", "all"):
        deleted["chat_messages"] = db.query(ChatMessage).delete(synchronize_session=False)
        deleted["chat_sessions"] = db.query(ChatSession).delete(synchronize_session=False)

    if body.scope == "all":
        deleted["file_versions"] = db.query(FileVersion).delete(synchronize_session=False)
        deleted["files"] = db.query(File).delete(synchronize_session=False)
        deleted["projects"] = db.query(Project).delete(synchronize_session=False)

    db.commit()

    if body.scope == "all":
        _wipe_storage_dir()

    return AdminResetOut(scope=body.scope, deleted=deleted)
