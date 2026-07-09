"""Validation des uploads + chemins de stockage sûrs (anti path-traversal)."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import AppError

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\- ]+")


def safe_filename(raw: str) -> str:
    """Normalise un nom de fichier : retire les caractères non sûrs, garde l'extension."""
    name = Path(raw or "fichier").name
    name = _SAFE_NAME_RE.sub("_", name)
    name = name.strip(" ._") or "fichier"
    return name[:200]


def safe_storage_join(root: Path, *parts: str) -> Path:
    """Concatène des morceaux de chemin et vérifie qu'on reste sous `root`."""
    root_resolved = root.resolve()
    candidate = (root_resolved.joinpath(*parts)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as e:
        raise AppError(
            "PATH_TRAVERSAL",
            "Chemin de stockage refusé (path traversal).",
            status_code=400,
        ) from e
    return candidate


def read_and_validate(
    upload: UploadFile,
    *,
    max_size: int,
    allowed_exts: set[str] | None = None,
    blocked_exts: set[str] | None = None,
) -> tuple[bytes, str, str]:
    """Lit le payload, vérifie taille + extension, renvoie (bytes, safe_name, ext lowercase)."""
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
            f"Extension refusée : {ext}",
            status_code=400,
            detail={"extension": ext},
        )

    if allowed_exts is not None and ext not in allowed_exts:
        raise AppError(
            "FILE_EXT_NOT_ALLOWED",
            f"Extension non autorisée : {ext}. Acceptées : {sorted(allowed_exts)}.",
            status_code=400,
            detail={"extension": ext, "allowed": sorted(allowed_exts)},
        )

    return raw, safe_name, ext
