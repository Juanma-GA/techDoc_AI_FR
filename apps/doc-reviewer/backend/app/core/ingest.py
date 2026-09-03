"""Ingestion universelle with automatic source and working formats.

Doc Reviewer accepte `.pdf`, `.doc`, `.docx` (et des `.zip` en contenant).
PDF and DOCX remain native working files; legacy DOC is retained as the
original and converted to a DOCX working copy.

Garde-fous anti zip-bomb : taille par fichier, taille decompressee totale et
nombre de fichiers bornes (repris de word-reviewer).
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.core import doc_convert
from app.core.errors import AppError
from app.core.security import safe_filename, validate_pdf_bytes

log = logging.getLogger("doc_reviewer.ingest")

SUPPORTED_EXTS = (".pdf", ".doc", ".docx")

MAX_FILES = 300
MAX_TOTAL_UNCOMPRESSED = 800 * 1024 * 1024  # 800 MB decompresses


@dataclass(frozen=True)
class PreparedDocument:
    source_format: str
    working_format: str
    original_bytes: bytes
    working_bytes: bytes
    filename: str
    convert_engine: str


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


def to_pdf_bytes(name: str, data: bytes) -> tuple[bytes, str, str]:
    """Normalise un fichier supporte en octets **PDF**.

    - `.pdf`  : valide (magic bytes + taille) et renvoie tel quel.
    - `.doc/.docx` : convertit en PDF fidele (LibreOffice prioritaire, repli Word).

    Retourne `(pdf_bytes, display_name, engine)`. `engine` trace le moteur de
    normalisation : `"pdf"` (natif, aucune conversion), `"libreoffice"` ou
    `"word"`. Le `display_name` conserve le nom d'origine (le rendu PDF garde
    l'extension source pour la tracabilite).
    """
    safe = safe_filename(name)
    ext = Path(safe).suffix.lower()
    if ext == ".pdf":
        validate_pdf_bytes(data, _max_single())
        return data, safe, "pdf"
    if ext in (".doc", ".docx"):
        if len(data) == 0:
            raise AppError("UPLOAD_EMPTY", "Fichier vide", status_code=400)
        if len(data) > _max_single():
            raise AppError("FILE_TOO_LARGE", f"{safe} depasse la taille max.", status_code=413)
        pdf_bytes, engine = doc_convert.doc_to_pdf_bytes(data, ext)
        return pdf_bytes, safe, engine
    raise AppError(
        "UNSUPPORTED_FORMAT",
        f"Format non supporte : {ext or '?'} (attendu .pdf / .doc / .docx)",
        status_code=400,
    )


def prepare_document(name: str, data: bytes) -> PreparedDocument:
    """Validate and prepare an upload without applying any document edits.

    PDF and DOCX remain in their native working format. Legacy DOC is retained
    as the original and converted once to DOCX for analysis and corrections.
    """
    safe = safe_filename(name)
    ext = Path(safe).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise AppError(
            "UNSUPPORTED_FORMAT",
            f"Format non supporte : {ext or '?'} (attendu .pdf / .doc / .docx)",
            status_code=400,
        )
    if not data:
        raise AppError("UPLOAD_EMPTY", "Fichier vide", status_code=400)
    if len(data) > _max_single():
        raise AppError("FILE_TOO_LARGE", f"{safe} depasse la taille max.", status_code=413)
    if ext == ".pdf":
        validate_pdf_bytes(data, _max_single())
        try:
            import fitz

            pdf = fitz.open(stream=data, filetype="pdf")
            pdf.close()
        except Exception as exc:  # noqa: BLE001
            raise AppError("PDF_INVALID", "PDF illisible", status_code=400) from exc
        return PreparedDocument("pdf", "pdf", data, data, safe, "pdf")
    if ext == ".docx":
        if not data.startswith(b"PK"):
            raise AppError("DOCX_INVALID", "Fichier .docx illisible (OOXML attendu).", status_code=400)
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "[Content_Types].xml" not in archive.namelist():
                    raise ValueError("OOXML content types missing")
        except (zipfile.BadZipFile, ValueError) as exc:
            raise AppError("DOCX_INVALID", "Fichier .docx illisible.", status_code=400) from exc
        return PreparedDocument("docx", "docx", data, data, safe, "docx-native")
    working = doc_convert.office_to_docx_bytes(data, ".doc")
    return PreparedDocument("doc", "docx", data, working, safe, "libreoffice")
