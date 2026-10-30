"""Atomic local writes and best-effort cleanup after database commits."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from uuid import uuid4

import structlog

log = structlog.get_logger(__name__)
# Windows can reject simultaneous replacements of the same destination.
_PUBLISH_LOCK = Lock()


def remove_files(files: Iterable[Path], *, directories: Iterable[Path] = ()) -> None:
    for path in dict.fromkeys(files):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("file_cleanup_failed", path=str(path), error_type=type(exc).__name__, exc_info=True)
    for path in dict.fromkeys(directories):
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            log.warning("directory_cleanup_failed", path=str(path), error_type=type(exc).__name__, exc_info=True)


@contextmanager
def atomic_output_path(path: Path) -> Iterator[Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        with _PUBLISH_LOCK:
            os.replace(temporary, path)
    finally:
        remove_files([temporary])


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with atomic_output_path(path) as temporary:
        temporary.write_bytes(data)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def replace_directory(staging: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.{uuid4().hex}.bak")
    with _PUBLISH_LOCK:
        had_previous = destination.exists()
        if had_previous:
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except OSError:
            if had_previous:
                os.replace(backup, destination)
            raise
    if had_previous:
        remove_files([], directories=[backup])
