"""Validation des uploads + chemins de stockage surs (anti path-traversal)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from app.core.errors import AppError


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\- ]+")


def safe_filename(raw: str) -> str:
    """Normalise un nom de fichier : retire les caracteres non surs, garde l'extension."""
    name = Path(raw or "fichier").name
    name = _SAFE_NAME_RE.sub("_", name)
    name = name.strip(" ._") or "fichier"
    return name[:200]


def safe_storage_join(root: Path, *parts: str) -> Path:
    """Concatene des morceaux de chemin et verifie qu'on reste sous `root`."""
    root_resolved = root.resolve()
    candidate = (root_resolved.joinpath(*parts)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as e:
        raise AppError(
            "PATH_TRAVERSAL",
            "Chemin de stockage refuse (path traversal).",
            status_code=400,
        ) from e
    return candidate


def safe_under_root(root: str, candidate: str) -> Path:
    """Verifie qu'un chemin absolu/relatif reste confine sous `root` (racine OneDrive).

    Generalise `safe_storage_join` a une racine arbitraire configuree par
    l'utilisateur (input ou output OneDrive). Un `candidate` vide renvoie la
    racine elle-meme. Resout `~` et les `..` avant comparaison.
    """
    if not root or not root.strip():
        raise AppError(
            "ROOT_NOT_CONFIGURED",
            "Racine OneDrive non configuree. Renseignez-la dans Parametres.",
            status_code=400,
        )
    root_resolved = Path(os.path.expanduser(root.strip())).resolve()
    cand = (candidate or "").strip()
    if not cand:
        return root_resolved
    cand_expanded = Path(os.path.expanduser(cand))
    # Un chemin absolu doit deja etre sous la racine ; un relatif est joint a la racine.
    base = cand_expanded if cand_expanded.is_absolute() else root_resolved / cand_expanded
    resolved = base.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as e:
        raise AppError(
            "PATH_OUTSIDE_ROOT",
            "Chemin refuse : hors de la racine OneDrive configuree.",
            status_code=400,
            detail={"root": str(root_resolved)},
        ) from e
    return resolved


def read_and_validate(
    upload: UploadFile,
    *,
    max_size: int,
    allowed_exts: Optional[set[str]] = None,
    blocked_exts: Optional[set[str]] = None,
) -> tuple[bytes, str, str]:
    """Lit le payload, verifie taille + extension, renvoie (bytes, safe_name, ext lowercase)."""
    raw = upload.file.read()
    if len(raw) > max_size:
        raise AppError(
            "FILE_TOO_LARGE",
            f"Fichier trop volumineux (> {max_size // (1024 * 1024)} Mo).",
            status_code=413,
            detail={"size": len(raw), "max": max_size},
        )
    if not raw:
        raise AppError("FILE_EMPTY", "Fichier vide.", status_code=400)

    safe_name = safe_filename(upload.filename or "fichier")
    ext = Path(safe_name).suffix.lower()

    if blocked_exts and ext in blocked_exts:
        raise AppError(
            "FILE_EXT_BLOCKED",
            f"Extension refusee : {ext}",
            status_code=400,
            detail={"extension": ext},
        )

    if allowed_exts is not None and ext not in allowed_exts:
        raise AppError(
            "FILE_EXT_NOT_ALLOWED",
            f"Extension non autorisee : {ext}. Acceptees : {sorted(allowed_exts)}.",
            status_code=400,
            detail={"extension": ext, "allowed": sorted(allowed_exts)},
        )

    return raw, safe_name, ext
