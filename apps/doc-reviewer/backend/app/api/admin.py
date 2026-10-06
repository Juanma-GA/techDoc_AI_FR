"""Admin endpoints — nuclear reset of the document/suggestion store.

Two endpoints, both destructive and irreversible :

- `POST /admin/wipe-suggestions` deletes every Suggestion row
  regardless of status (open, rejected, accepted, edited, applied).
  Custom Rule definitions, AppConfig and built-in Standards are
  preserved. EditHistory rows are kept too (they reference applied
  versions that already shipped on disk).
- `POST /admin/reset` is the full reset : every Document is dropped
    (cascading to suggestions, runs, history), user rules and compiled
    checklists are deleted, every snapshot file in `storage/document_*/`
    is removed, and orphan storage folders are cleaned up. Built-in
    Standards, Mistral config and the AI prompt are preserved.

Both endpoints are local-first (palier 1 auth — bind 127.0.0.1) and
deliberately have no authentication gate. Don't expose them on a
public bind.
"""

import os
import shutil
import stat
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import CompiledRuleVersion, Document, EditHistory, Rule, Suggestion
from app.db.session import get_db


router = APIRouter(prefix="/admin", tags=["admin"])
_logger = structlog.get_logger(__name__)


def _doc_storage_root() -> Path:
    return Path(settings.storage_dir)


def _force_remove(func, path, _exc):
    """rmtree onerror/onexc handler — clears the read-only bit and
    retries. Required on Windows where `v0.pdf` is set RO at init."""
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass
    func(path)


def _rmtree(target: Path) -> None:
    """Cross-platform rmtree that handles read-only files (Windows)."""
    # Python ≥ 3.12 deprecated `onerror` in favour of `onexc`. Try the
    # new keyword first, fall back to the old name to stay compatible.
    try:
        shutil.rmtree(target, onexc=_force_remove)  # type: ignore[call-arg]
    except TypeError:
        shutil.rmtree(target, onerror=_force_remove)  # type: ignore[arg-type]


def _remove_storage_dir(storage_dir: str) -> bool:
    """Remove `storage_dir/document_<id>/` from disk. Returns True on
    success, False if the dir didn't exist or couldn't be removed.
    Never raises — file system failures degrade gracefully."""
    target = _doc_storage_root() / storage_dir
    if not target.exists():
        return False
    try:
        _rmtree(target)
        return True
    except OSError as exc:
        _logger.warning(
            "admin_storage_cleanup_failed",
            error=type(exc).__name__,
        )
        return False


@router.post("/wipe-suggestions")
def wipe_all_suggestions(db: Session = Depends(get_db)) -> dict:
    """Delete every Suggestion row, all statuses included.

    Use this when you want to clear the analysis state on a corpus
    without touching the documents or their applied edits."""
    total = db.scalar(select(Suggestion).limit(1))
    if total is None:
        return {"deleted": 0}
    result = db.execute(delete(Suggestion))
    db.commit()
    deleted = result.rowcount if result.rowcount is not None else 0
    _logger.info("admin_wipe_suggestions", deleted=deleted)
    return {"deleted": deleted}


@router.post("/reset")
def reset_all(db: Session = Depends(get_db)) -> dict:
    """Nuclear reset : drop every Document (cascades suggestions, runs,
    history), user rules and compiled checklists, then remove their
    storage folders from disk. Orphan
    storage folders (no matching Document row) are also cleaned up.
    Returns a count summary so the UI can confirm the wipe scope."""
    docs = list(db.scalars(select(Document)))
    known_storage_dirs = {d.storage_dir for d in docs}
    deleted_docs = len(docs)
    deleted_rules = db.execute(delete(Rule)).rowcount or 0
    deleted_checklist_rules = (
        db.execute(
            delete(CompiledRuleVersion).where(
                CompiledRuleVersion.source == "user_checklist"
            )
        ).rowcount
        or 0
    )

    # 1. Delete docs in bulk — cascade=all,delete-orphan will wipe
    #    suggestions / analysis_runs / edit_history transparently.
    for doc in docs:
        db.delete(doc)
    db.commit()

    # 2. Clean known storage folders.
    cleaned = 0
    for sd in known_storage_dirs:
        if _remove_storage_dir(sd):
            cleaned += 1

    # 3. Sweep orphan storage folders that survived an earlier
    #    interruption (e.g. delete_document was called before this fix
    #    added disk cleanup).
    root = _doc_storage_root()
    orphans = 0
    if root.is_dir():
        for child in root.iterdir():
            if not child.is_dir() or not child.name.startswith("document_"):
                continue
            if child.name in known_storage_dirs:
                continue
            try:
                _rmtree(child)
                orphans += 1
            except OSError as exc:
                _logger.warning(
                    "admin_orphan_cleanup_failed",
                    error=type(exc).__name__,
                )

    _logger.info(
        "admin_reset",
        documents_deleted=deleted_docs,
        storage_cleaned=cleaned,
        orphans_cleaned=orphans,
    )
    return {
        "documents_deleted": deleted_docs,
        "rules_deleted": deleted_rules,
        "checklist_rules_deleted": deleted_checklist_rules,
        "storage_folders_cleaned": cleaned,
        "orphan_folders_cleaned": orphans,
    }
