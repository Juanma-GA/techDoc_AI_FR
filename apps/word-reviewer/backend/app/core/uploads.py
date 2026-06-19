"""Extraction des .docx d'un upload : un fichier, plusieurs, ou un .zip.

Garde-fous anti zip-bomb : taille par fichier, taille decompressee totale et
nombre de fichiers bornes. Les entrees non .docx sont ignorees (tracees).
"""

from __future__ import annotations

import io
import zipfile

from app.config import settings
from app.core.errors import AppError


MAX_FILES = 300
MAX_TOTAL_UNCOMPRESSED = 800 * 1024 * 1024  # 800 MB decompresses


def _max_single() -> int:
    return settings.max_upload_size_bytes


def _basename(name: str) -> str:
    return name.replace("\\", "/").rsplit("/", 1)[-1]


def _is_word(name: str) -> bool:
    base = _basename(name)
    return base.lower().endswith((".docx", ".doc")) and not base.startswith(".")


def extract_uploads(items: list[tuple[str, bytes]]) -> tuple[list[tuple[str, bytes]], list[str]]:
    """(fichiers Word [(nom, octets)], ignores [noms]). Accepte .docx et .doc
    (le .doc sera converti a l'etape suivante)."""
    docs: list[tuple[str, bytes]] = []
    ignored: list[str] = []
    for fname, data in items:
        low = fname.lower()
        if low.endswith(".zip"):
            d, i = _extract_zip(data)
            docs.extend(d)
            ignored.extend(i)
        elif low.endswith((".docx", ".doc")):
            if len(data) > _max_single():
                raise AppError("FILE_TOO_LARGE", f"{_basename(fname)} depasse la taille max.", 413)
            docs.append((_basename(fname), data))
        else:
            ignored.append(fname)
    if len(docs) > MAX_FILES:
        raise AppError("TOO_MANY_FILES", f"Plus de {MAX_FILES} fichiers dans l'upload.", 413)
    if not docs:
        raise AppError("NO_DOCX", "Aucun fichier .docx / .doc trouve dans l'upload.", 400)
    return docs, ignored


def _extract_zip(data: bytes) -> tuple[list[tuple[str, bytes]], list[str]]:
    out: list[tuple[str, bytes]] = []
    ignored: list[str] = []
    total = 0
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise AppError("BAD_ZIP", "Archive .zip illisible.", 400) from exc
    with zf:
        for info in zf.infolist():
            if info.is_dir() or "__MACOSX" in info.filename:
                continue
            if not _is_word(info.filename):
                ignored.append(info.filename)
                continue
            if info.file_size > _max_single():
                raise AppError("FILE_TOO_LARGE", f"{info.filename} (decompresse) trop volumineux.", 413)
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED:
                raise AppError("ZIP_TOO_LARGE", "Taille decompressee totale excessive.", 413)
            out.append((_basename(info.filename), zf.read(info)))
    return out, ignored
