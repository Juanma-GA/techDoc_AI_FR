"""Bounded streaming uploads with content hashes and temporary-file cleanup."""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import BinaryIO

from app.core.errors import AppError
from app.core.fs import remove_files

UPLOAD_LOCK = RLock()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def staged_upload(
    stream: BinaryIO,
    directory: Path,
    limit: int,
    *,
    suffix: str = ".upload.tmp",
) -> Iterator[tuple[Path, str]]:
    directory.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=directory, prefix=".upload-", suffix=suffix, delete=False) as output:
        path = Path(output.name)
    try:
        digest = hashlib.sha256()
        size = 0
        with path.open("wb") as output:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise AppError("FILE_TOO_LARGE", "Document trop volumineux.", 413)
                digest.update(chunk)
                output.write(chunk)
        yield path, digest.hexdigest()
    finally:
        remove_files([path])
