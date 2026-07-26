"""Per-document PDF snapshot store.

Layout on disk (under `settings.storage_dir`):

    document_<id>/
        v0.pdf            # original, immutable
        v1.pdf            # after first applied suggestion
        v2.pdf
        ...

Public API:

- `init_storage(doc)`     — create folder + write V0 from raw bytes.
- `path_for(doc, n)`      — absolute path for vN.pdf.
- `current_path(doc)`     — vN where N == doc.current_version.
- `bump_version(doc, src)` — copy src -> v(N+1).pdf and return new path/N.
"""

from __future__ import annotations

import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.core.errors import AppError
from app.core.security import safe_storage_join


@dataclass
class SnapshotResult:
    new_version: int
    snapshot_path: Path


def _doc_dir(storage_dir_value: str) -> Path:
    root = Path(settings.storage_dir)
    return safe_storage_join(root, storage_dir_value)


def init_storage(storage_dir_value: str, raw_pdf: bytes) -> Path:
    """Create per-document folder and persist V0 (immutable)."""
    doc_dir = _doc_dir(storage_dir_value)
    doc_dir.mkdir(parents=True, exist_ok=True)
    v0 = doc_dir / "v0.pdf"
    v0.write_bytes(raw_pdf)
    try:
        v0.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        # Best-effort: filesystem may not support chmod (Windows non-NTFS).
        pass
    return v0


def path_for(storage_dir_value: str, version: int) -> Path:
    if version < 0:
        raise AppError("VERSION_INVALID", "Version PDF invalide", status_code=400)
    return _doc_dir(storage_dir_value) / f"v{version}.pdf"


def current_path(storage_dir_value: str, current_version: int) -> Path:
    p = path_for(storage_dir_value, current_version)
    if not p.is_file():
        raise AppError(
            "PDF_VERSION_MISSING",
            f"Snapshot v{current_version} introuvable sur disque",
            status_code=500,
        )
    return p


def bump_version(storage_dir_value: str, current_version: int) -> SnapshotResult:
    """Copy current snapshot to v(N+1).pdf and return the new version & path.

    Caller is expected to mutate the copy *after* this call.
    """
    src = current_path(storage_dir_value, current_version)
    new_version = current_version + 1
    dst = path_for(storage_dir_value, new_version)
    shutil.copyfile(src, dst)
    return SnapshotResult(new_version=new_version, snapshot_path=dst)
