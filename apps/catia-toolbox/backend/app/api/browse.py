"""Routes /api/v1/browse - navigation lazy de l'arborescence OneDrive (locale).

ECART STANDARD assume (meme perimetre que `/imports/scan`, README ## Ecarts) :
lecture du systeme de fichiers hors `data/storage/`, confinee sous la racine
OneDrive configuree (input | output). Metadonnees uniquement (nom, taille,
mtime, extension), jamais le contenu ; liens symboliques ignores ; un seul
niveau par appel (lazy tree). Aucune ecriture.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import onedrive
from app.core import parser as parser_mod
from app.core.errors import AppError
from app.core.security import safe_under_root
from app.db.session import get_db
from app.schemas import BrowseEntryOut, BrowseListIn, BrowseListOut, BrowseRootsOut


log = logging.getLogger("catia_toolbox.browse")

router = APIRouter(prefix="/browse", tags=["browse"])


@router.get("/roots", response_model=BrowseRootsOut)
def browse_roots(db: Session = Depends(get_db)) -> BrowseRootsOut:
    roots = onedrive.get_onedrive_roots(db)
    return BrowseRootsOut(
        input=roots["input"],
        output=roots["output"],
        detected=onedrive.detect_onedrive_roots(),
    )


@router.post("/list", response_model=BrowseListOut)
def browse_list(payload: BrowseListIn, db: Session = Depends(get_db)) -> BrowseListOut:
    if payload.scope not in ("input", "output"):
        raise AppError("BROWSE_SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)

    root = onedrive.root_for_scope(db, payload.scope)
    target = safe_under_root(root, payload.path)  # leve si non configure / hors racine

    if not target.exists():
        raise AppError(
            "BROWSE_PATH_NOT_FOUND",
            "Le dossier n'existe pas.",
            status_code=404,
            detail={"path": str(target)},
        )
    if not target.is_dir():
        raise AppError(
            "BROWSE_PATH_NOT_DIR",
            "Le chemin n'est pas un dossier.",
            status_code=400,
            detail={"path": str(target)},
        )

    entries: list[BrowseEntryOut] = []
    try:
        with os.scandir(target) as it:
            for de in it:
                try:
                    if de.is_symlink():
                        continue
                    is_dir = de.is_dir()
                except OSError:
                    continue
                entries.append(
                    BrowseEntryOut(
                        name=de.name,
                        path=str(target / de.name),
                        kind="folder" if is_dir else "file",
                        ext="" if is_dir else PurePath(de.name).suffix.lstrip(".").lower(),
                        size=_safe_size(de),
                        mtime=_safe_mtime(de),
                    )
                )
    except OSError as e:
        raise AppError(
            "BROWSE_READ_FAILED",
            "Lecture du dossier impossible.",
            status_code=400,
            detail={"path": str(target)},
        ) from e

    # Dossiers d'abord, puis tri alphabetique insensible a la casse.
    entries.sort(key=lambda e: (e.kind != "folder", e.name.lower()))
    return BrowseListOut(scope=payload.scope, root=root, path=str(target), entries=entries)


@router.post("/files", response_model=BrowseListOut)
def browse_files(payload: BrowseListIn, db: Session = Depends(get_db)) -> BrowseListOut:
    """Liste a plat tous les fichiers (recursif) sous un dossier, pour choisir
    des fichiers precis sans importer le dossier entier."""
    if payload.scope not in ("input", "output"):
        raise AppError("BROWSE_SCOPE_INVALID", "scope attendu : input ou output.", status_code=400)

    root = onedrive.root_for_scope(db, payload.scope)
    target = safe_under_root(root, payload.path)

    if not target.exists():
        raise AppError("BROWSE_PATH_NOT_FOUND", "Le dossier n'existe pas.", status_code=404, detail={"path": str(target)})
    if not target.is_dir():
        raise AppError("BROWSE_PATH_NOT_DIR", "Le chemin n'est pas un dossier.", status_code=400, detail={"path": str(target)})

    entries = [
        BrowseEntryOut(
            name=f["name"],
            path=f["path"],
            kind="file",
            ext=f["ext"],
            size=f["size"],
            mtime=f["mtime"],
            rel=f["rel"],
        )
        for f in parser_mod.list_files(str(target))
    ]
    entries.sort(key=lambda e: e.rel.lower())
    return BrowseListOut(scope=payload.scope, root=root, path=str(target), entries=entries)


def _safe_size(de: os.DirEntry) -> int:
    try:
        return int(de.stat(follow_symlinks=False).st_size) if de.is_file() else 0
    except OSError:
        return 0


def _safe_mtime(de: os.DirEntry) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(de.stat(follow_symlinks=False).st_mtime, tz=timezone.utc)
    except OSError:
        return None
