"""Ingestion universelle -> PDF fidele.

Doc Reviewer accepte `.pdf`, `.doc`, `.docx` (et des `.zip` en contenant). Quel
que soit le format, la detection tourne sur un **PDF** :
- `.pdf`  -> utilise tel quel (zero conversion) ;
- `.doc/.docx` -> **PDF fidele** via `doc_convert.convert_to_pdf` (Word COM exact,
  repli LibreOffice) -> plus d'artefacts de conversion `.doc -> .docx` lossy.

Garde-fous anti zip-bomb : taille par fichier, taille decompressee totale et
nombre de fichiers bornes (repris de word-reviewer).
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

from app.config import settings
from app.core import doc_convert
from app.core.errors import AppError
from app.core.security import safe_filename, validate_pdf_bytes

log = logging.getLogger("doc_reviewer.ingest")

SUPPORTED_EXTS = (".pdf", ".doc", ".docx")

MAX_FILES = 300
MAX_TOTAL_UNCOMPRESSED = 800 * 1024 * 1024  # 800 MB decompresses


def _max_single() -> int:
    return settings.max_upload_size_bytes


def _basename(name: str) -> str:
    return name.replace("\\", "/").rsplit("/", 1)[-1]


def _is_supported(name: str) -> bool:
    base = _basename(name)
    return base.lower().endswith(SUPPORTED_EXTS) and not base.startswith(".")


def expand_uploads(items: list[tuple[str, bytes]]) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Etend les uploads en fichiers supportes : passe-plat pour `.pdf/.doc/.docx`,
    extraction recursive des `.zip`. Retourne `(fichiers [(nom, octets)], ignores)`.
    """
    out: list[tuple[str, bytes]] = []
    ignored: list[str] = []
    for fname, data in items:
        low = fname.lower()
        if low.endswith(".zip"):
            d, i = _extract_zip(data)
            out.extend(d)
            ignored.extend(i)
        elif _is_supported(fname):
            if len(data) > _max_single():
                raise AppError("FILE_TOO_LARGE", f"{_basename(fname)} depasse la taille max.", status_code=413)
            out.append((_basename(fname), data))
        else:
            ignored.append(fname)
    if len(out) > MAX_FILES:
        raise AppError("TOO_MANY_FILES", f"Plus de {MAX_FILES} fichiers dans l'upload.", status_code=413)
    if not out:
        raise AppError(
            "NO_SUPPORTED_FILE",
            "Aucun fichier .pdf / .doc / .docx trouve dans l'upload.",
            status_code=400,
        )
    return out, ignored


def _extract_zip(data: bytes) -> tuple[list[tuple[str, bytes]], list[str]]:
    out: list[tuple[str, bytes]] = []
    ignored: list[str] = []
    total = 0
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise AppError("BAD_ZIP", "Archive .zip illisible.", status_code=400) from exc
    with zf:
        for info in zf.infolist():
            if info.is_dir() or "__MACOSX" in info.filename:
                continue
            if not _is_supported(info.filename):
                ignored.append(info.filename)
                continue
            if info.file_size > _max_single():
                raise AppError("FILE_TOO_LARGE", f"{info.filename} (decompresse) trop volumineux.", status_code=413)
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED:
                raise AppError("ZIP_TOO_LARGE", "Taille decompressee totale excessive.", status_code=413)
            out.append((_basename(info.filename), zf.read(info)))
    return out, ignored


def to_pdf_bytes(name: str, data: bytes) -> tuple[bytes, str]:
    """Normalise un fichier supporte en octets **PDF**.

    - `.pdf`  : valide (magic bytes + taille) et renvoie tel quel.
    - `.doc/.docx` : convertit en PDF fidele (Word COM / LibreOffice).

    Retourne `(pdf_bytes, display_name)`. Le `display_name` conserve le nom
    d'origine (le rendu PDF garde l'extension source pour la tracabilite).
    """
    safe = safe_filename(name)
    ext = Path(safe).suffix.lower()
    if ext == ".pdf":
        validate_pdf_bytes(data, _max_single())
        return data, safe
    if ext in (".doc", ".docx"):
        if len(data) == 0:
            raise AppError("UPLOAD_EMPTY", "Fichier vide", status_code=400)
        if len(data) > _max_single():
            raise AppError("FILE_TOO_LARGE", f"{safe} depasse la taille max.", status_code=413)
        pdf_bytes = doc_convert.doc_to_pdf_bytes(data, ext)
        return pdf_bytes, safe
    raise AppError(
        "UNSUPPORTED_FORMAT",
        f"Format non supporte : {ext or '?'} (attendu .pdf / .doc / .docx)",
        status_code=400,
    )
