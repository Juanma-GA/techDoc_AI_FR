"""Versioned raster thumbnails for the wizard image gallery."""

from pathlib import Path

import pymupdf as fitz

from app.core.errors import AppError
from app.core.fs import atomic_write_bytes


def thumbnail_path(source: Path, size: int) -> Path:
    stat = source.stat()
    destination = (
        source.parent / ".thumbnails" / (f"{source.name}.{stat.st_mtime_ns}.{stat.st_size}.{size}.jpg")
    )
    if not destination.is_file():
        try:
            with fitz.open(str(source)) as image:
                page = image[0]
                scale = min(1.0, size / max(page.rect.width, page.rect.height))
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                atomic_write_bytes(destination, pixmap.tobytes("jpg"))
        except (OSError, RuntimeError, ValueError) as exc:
            raise AppError("IMAGE_PREVIEW_FAILED", "Impossible de produire la vignette.", 500) from exc
    return destination
