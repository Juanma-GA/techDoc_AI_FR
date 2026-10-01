"""Security helpers for file handling and outbound service URLs."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import UploadFile

from app.core.errors import AppError


_FILENAME_BAD_CHARS = re.compile(r"[^A-Za-z0-9._\- ()]+")
_MAX_FILENAME_LEN = 180

_MAGIC_PDF = b"%PDF-"
_MISTRAL_ALLOWED_HOSTS = frozenset({"api.mistral.ai"})
_MISTRAL_ENTERPRISE_HOST = re.compile(
    r"api\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.dc\.mistral\.ai"
)


def validate_mistral_base_url(raw: str) -> str:
    """Allow the canonical Mistral API and enterprise HTTPS origins."""
    if not isinstance(raw, str) or not raw or len(raw) > 2048 or raw != raw.strip():
        raise ValueError("URL Mistral non autorisée")
    if any(char.isspace() or ord(char) < 0x20 for char in raw):
        raise ValueError("URL Mistral non autorisée")

    try:
        parsed = urlsplit(raw)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL Mistral non autorisée") from exc

    if (
        parsed.scheme.lower() != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or "?" in raw
        or "#" in raw
        or port not in {None, 443}
    ):
        raise ValueError("URL Mistral non autorisée")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
        or address.is_multicast
    ):
        raise ValueError("URL Mistral non autorisée")

    normalized_host = host.rstrip(".").lower()
    if address is not None or (
        normalized_host not in _MISTRAL_ALLOWED_HOSTS
        and _MISTRAL_ENTERPRISE_HOST.fullmatch(normalized_host) is None
    ):
        raise ValueError("URL Mistral non autorisée")
    return f"https://{normalized_host}"


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


def _check_upload_size(upload: UploadFile, max_size: int) -> None:
    size = getattr(upload, "size", None)
    if size is None:
        file = upload.file
        try:
            position = file.tell()
            file.seek(0, 2)
            size = file.tell()
            file.seek(position)
        except (AttributeError, OSError, ValueError):
            size = None
    if size is not None and size > max_size:
        raise AppError("FILE_TOO_LARGE", "Fichier trop volumineux.", status_code=413)


def read_upload_bounded(upload: UploadFile, max_size: int) -> bytes:
    _check_upload_size(upload, max_size)
    raw = upload.file.read(max_size + 1)
    if len(raw) > max_size:
        raise AppError("FILE_TOO_LARGE", "Fichier trop volumineux.", status_code=413)
    return raw


async def read_upload_bounded_async(upload: UploadFile, max_size: int) -> bytes:
    _check_upload_size(upload, max_size)
    raw = await upload.read(max_size + 1)
    if len(raw) > max_size:
        raise AppError("FILE_TOO_LARGE", "Fichier trop volumineux.", status_code=413)
    return raw


def read_and_validate_pdf(upload: UploadFile, max_size: int) -> tuple[bytes, str]:
    safe_name = safe_filename(upload.filename)
    ext = Path(safe_name).suffix.lower()
    if ext != ".pdf":
        raise AppError("UPLOAD_BAD_EXT", "Extension non supportée — PDF uniquement", status_code=400)
    raw = read_upload_bounded(upload, max_size)
    validate_pdf_bytes(raw, max_size)
    return raw, safe_name
