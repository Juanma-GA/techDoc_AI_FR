"""Upload security helpers — sanitize filenames, magic-bytes MIME validation,
path-traversal guard. Same semantics as legacy hotfix."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import AppError


_FILENAME_BAD_CHARS = re.compile(r"[^A-Za-z0-9._\- ()]+")
_MAX_FILENAME_LEN = 180


def safe_filename(raw: str | None) -> str:
    if not raw:
        return "upload.bin"
    base = Path(raw).name.replace("\x00", "")
    base = _FILENAME_BAD_CHARS.sub("_", base).strip(" .")
    if not base or base in {".", ".."}:
        base = "upload.bin"
    return base[:_MAX_FILENAME_LEN]


def safe_storage_join(root: Path, *parts: str) -> Path:
    root_resolved = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise AppError("UPLOAD_PATH_INVALID", "Chemin de stockage invalide",
                       status_code=400) from exc
    return candidate


_MAGIC_PDF = b"%PDF-"
_MAGIC_ZIP = b"PK\x03\x04"


def _looks_like_xml(head: bytes) -> bool:
    s = head.lstrip()[:200].lower()
    return s.startswith(b"<?xml") or s.startswith(b"<")


def _looks_like_text(head: bytes) -> bool:
    if not head or b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            head.decode("latin-1")
            return True
        except UnicodeDecodeError:
            return False


# Magic-bytes pour quelques formats binaires courants.
_MAGIC_PNG  = b"\x89PNG\r\n\x1a\n"
_MAGIC_JPEG = b"\xff\xd8\xff"
_MAGIC_GIF  = b"GIF8"
_MAGIC_WEBP = b"RIFF"
_MAGIC_BMP  = b"BM"


_EXT_TO_VALIDATOR = {
    ".pdf":    lambda h: h.startswith(_MAGIC_PDF),
    ".docx":   lambda h: h.startswith(_MAGIC_ZIP),
    ".xlsx":   lambda h: h.startswith(_MAGIC_ZIP),
    ".xlsm":   lambda h: h.startswith(_MAGIC_ZIP),
    ".pptx":   lambda h: h.startswith(_MAGIC_ZIP),
    ".xml":    _looks_like_xml,
    ".s1000d": _looks_like_xml,
    ".html":   _looks_like_text,
    ".htm":    _looks_like_text,
    ".csv":    _looks_like_text,
    # Pas de validation magic pour les types texte purs : on accepte tout
    # (.txt, .md, .json, .yaml, .yml, .log, .rtf, .py, .js, etc.) et c'est
    # la passe d'analyse qui flagge les types inattendus si l'utilisateur a
    # configuré `types_fichiers_attendus`.
    ".png":  lambda h: h.startswith(_MAGIC_PNG),
    ".jpg":  lambda h: h.startswith(_MAGIC_JPEG),
    ".jpeg": lambda h: h.startswith(_MAGIC_JPEG),
    ".gif":  lambda h: h.startswith(_MAGIC_GIF),
    ".webp": lambda h: h.startswith(_MAGIC_WEBP),
    ".bmp":  lambda h: h.startswith(_MAGIC_BMP),
}


def validate_upload_bytes(
    raw: bytes,
    declared_ext: str,
    allowed_exts: set[str] | None,
    max_size: int,
    blocked_exts: set[str] | None = None,
) -> None:
    if len(raw) == 0:
        raise AppError("UPLOAD_EMPTY", "Fichier vide", status_code=400)
    if len(raw) > max_size:
        raise AppError(
            "UPLOAD_TOO_LARGE",
            f"Fichier trop volumineux (>{max_size // (1024 * 1024)} Mo)",
            status_code=400,
        )

    ext = declared_ext.lower()
    if allowed_exts is not None and ext not in allowed_exts:
        raise AppError("UPLOAD_BAD_EXT", f"Extension {ext} non supportée", status_code=400)
    if blocked_exts is not None and ext in blocked_exts:
        raise AppError(
            "UPLOAD_BAD_EXT",
            f"Extension {ext} interdite pour des raisons de sécurité",
            status_code=400,
        )

    validator = _EXT_TO_VALIDATOR.get(ext)
    if validator is None:
        return
    head = raw[:512]
    if not validator(head):
        raise AppError(
            "UPLOAD_MIME_MISMATCH",
            f"Le contenu du fichier ne correspond pas à l'extension {ext}",
            status_code=400,
        )


def read_and_validate(
    upload: UploadFile,
    allowed_exts: set[str] | None = None,
    max_size: int = 50 * 1024 * 1024,
    blocked_exts: set[str] | None = None,
) -> tuple[bytes, str, str]:
    safe_name = safe_filename(upload.filename)
    ext = Path(safe_name).suffix.lower()
    raw = upload.file.read()
    validate_upload_bytes(raw, ext, allowed_exts, max_size, blocked_exts=blocked_exts)
    return raw, safe_name, ext
