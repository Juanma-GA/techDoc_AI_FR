"""Stockage et versioning des .docx (simplifie vs pdf_versioning).

Layout : `<storage_dir>/document_<uuid_hex>/v<N>.docx`. La version 0 est
l'original uploade ; chaque application de patch ecrit `v<N+1>.docx`. Pas de
geometrie a gerer : un snapshot est juste un .docx.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.config import settings


def storage_root() -> Path:
    root = Path(settings.storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def doc_dir_name(doc_id_hex: str) -> str:
    return f"document_{doc_id_hex}"


def doc_dir(storage_dir: str) -> Path:
    return storage_root() / storage_dir


def version_path(storage_dir: str, version: int) -> Path:
    return doc_dir(storage_dir) / f"v{version}.docx"


def write_version(storage_dir: str, version: int, data: bytes) -> Path:
    d = doc_dir(storage_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = version_path(storage_dir, version)
    path.write_bytes(data)
    return path


def write_original(storage_dir: str, data: bytes, filename: str) -> Path:
    """Persist the uploaded source separately when the working file differs."""
    path = doc_dir(storage_dir) / f"original{Path(filename).suffix.lower()}"
    path.write_bytes(data)
    return path


def read_version(storage_dir: str, version: int) -> bytes:
    return version_path(storage_dir, version).read_bytes()
