"""Routes /api/v1/admin - stats globales + operations de reset.

Les chemins et reglages Composer (table app_config) sont preserves au reset.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.db.models import (
    ColorizationItem,
    ColorizationRun,
    ConversionItem,
    ConversionRun,
    DiffEntry,
    DiffRun,
    NomenclatureItem,
    NomenclatureRun,
    SmgxmlChange,
    SmgxmlRun,
    StructureImport,
    TreeNode,
)
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut


log = logging.getLogger("catia_toolbox.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    return AdminStatsOut(
        imports=db.scalar(select(func.count(StructureImport.id))) or 0,
        nodes=db.scalar(select(func.count(TreeNode.id))) or 0,
        diffs=db.scalar(select(func.count(DiffRun.id))) or 0,
        conversions=db.scalar(select(func.count(ConversionRun.id))) or 0,
        colorizations=db.scalar(select(func.count(ColorizationRun.id))) or 0,
        nomenclatures=db.scalar(select(func.count(NomenclatureRun.id))) or 0,
        smgxml_runs=db.scalar(select(func.count(SmgxmlRun.id))) or 0,
        total_size_bytes=db.scalar(select(func.coalesce(func.sum(TreeNode.size), 0))) or 0,
    )


def _purge(db: Session, *models) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for model in models:
        count = db.scalar(select(func.count()).select_from(model)) or 0
        db.query(model).delete()
        deleted[model.__tablename__] = int(count)
    db.commit()
    return deleted


def _purge_local_uploads() -> int:
    storage_root = Path(settings.storage_dir).expanduser().resolve()
    local_root = storage_root / "local"
    if local_root.is_symlink():
        raise AppError(
            "RESET_STORAGE_INVALID",
            "Le stockage local ne peut pas être supprimé en toute sécurité.",
            status_code=500,
        )
    if not local_root.exists():
        return 0
    if not local_root.is_dir():
        raise AppError(
            "RESET_STORAGE_INVALID",
            "Le stockage local ne peut pas être supprimé en toute sécurité.",
            status_code=500,
        )

    file_count = sum(1 for path in local_root.rglob("*") if path.is_file() and not path.is_symlink())
    shutil.rmtree(local_root)
    return file_count


# Tables filles (leaf-first) purgees avant StructureImport pour des compteurs exacts.
_RUN_TABLES = (
    DiffEntry,
    DiffRun,
    ConversionItem,
    ConversionRun,
    ColorizationItem,
    ColorizationRun,
)

# Tables du pipeline, independantes des imports (leaf-first).
_PIPELINE_TABLES = (
    NomenclatureItem,
    NomenclatureRun,
    SmgxmlChange,
    SmgxmlRun,
)


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    """Reset DB et copies locales sauf `app_config` et les sources OneDrive."""
    deleted = _purge(db, *_RUN_TABLES, *_PIPELINE_TABLES, TreeNode, StructureImport)
    deleted["local_upload_files"] = _purge_local_uploads()
    log.info("admin reset all : %s", deleted)
    return AdminResetOut(scope="all", deleted=deleted)


@router.post("/reset/{scope}", response_model=AdminResetOut)
def reset_scope(scope: str, db: Session = Depends(get_db)) -> AdminResetOut:
    if scope == "all":
        return reset_all(db)
    if scope == "imports":
        deleted = _purge(db, *_RUN_TABLES, TreeNode, StructureImport)
    elif scope == "runs":
        deleted = _purge(db, *_RUN_TABLES)
    elif scope == "pipeline":
        deleted = _purge(db, *_PIPELINE_TABLES)
    else:
        raise AppError(
            "RESET_SCOPE_INVALID",
            "Scope inconnu. Valeurs : all | imports | runs | pipeline.",
            status_code=400,
            detail={"scope": scope},
        )
    log.info("admin reset %s : %s", scope, deleted)
    return AdminResetOut(scope=scope, deleted=deleted)
