"""Upload security helpers — sanitize filenames, magic-bytes MIME validation,
path-traversal guard. PDF-only for this app."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import AppError


_FILENAME_BAD_CHARS = re.compile(r"[^A-Za-z0-9._\- ()]+")
_MAX_FILENAME_LEN = 180

_MAGIC_PDF = b"%PDF-"


def safe_filename(raw: str | None) -> str:
    if not raw:
        return "upload.pdf"
    base = Path(raw).name.replace("\x00", "")
    base = _FILENAME_BAD_CHARS.sub("_", base).strip(" .")
    if not base or base in {".", ".."}:
        base = "upload.pdf"
    return base[:_MAX_FILENAME_LEN]


def safe_storage_join(root: Path, *parts: str) -> Path:
    root_resolved = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise AppError(
            "UPLOAD_PATH_INVALID",
            "Chemin de stockage invalide",
            status_code=400,
        ) from exc
    return candidate


def validate_pdf_bytes(raw: bytes, max_size: int) -> None:
    if len(raw) == 0:
        raise AppError("UPLOAD_EMPTY", "Fichier vide", status_code=400)
    if len(raw) > max_size:
        raise AppError(
            "UPLOAD_TOO_LARGE",
            f"Fichier trop volumineux (>{max_size // (1024 * 1024)} Mo)",
            status_code=400,
        )
    head = raw[:512]
    if not head.startswith(_MAGIC_PDF):
        raise AppError(
            "UPLOAD_BAD_EXT",
            "Le fichier n'est pas un PDF valide",
            status_code=400,
        )


def read_and_validate_pdf(upload: UploadFile, max_size: int) -> tuple[bytes, str]:
    safe_name = safe_filename(upload.filename)
    ext = Path(safe_name).suffix.lower()
    if ext != ".pdf":
        raise AppError("UPLOAD_BAD_EXT", "Extension non supportée — PDF uniquement", status_code=400)
    raw = upload.file.read()
    validate_pdf_bytes(raw, max_size)
    return raw, safe_name
