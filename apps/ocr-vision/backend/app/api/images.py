"""Routes images/illustrations extraites : liste, service du fichier, suppression."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.db.models import ExtractedImage, ProjectTable
from app.db.session import get_db
from app.schemas import ImageOut

router = APIRouter(tags=["images"])


def _image_path(img: ExtractedImage) -> Path:
    return Path(settings.storage_dir) / img.project_table_id / img.filename


def _out(img: ExtractedImage) -> ImageOut:
    return ImageOut(
        id=img.id,
        source_filename=img.source_filename or "",
        filename=img.filename,
        page=img.page,
        url=f"/api/v1/images/{img.id}/file",
        created_at=img.created_at,
    )


@router.get("/project-tables/{table_id}/images", response_model=list[ImageOut])
def list_images(table_id: str, db: Session = Depends(get_db)) -> list[ImageOut]:
    if db.get(ProjectTable, table_id) is None:
        raise AppError("TABLE_NOT_FOUND", "Table introuvable.", status_code=404)
    rows = db.scalars(
        select(ExtractedImage)
        .where(ExtractedImage.project_table_id == table_id)
        .order_by(ExtractedImage.created_at.asc())
    ).all()
    return [_out(i) for i in rows]


@router.get("/images/{image_id}/file")
def get_image_file(image_id: str, db: Session = Depends(get_db)) -> FileResponse:
    img = db.get(ExtractedImage, image_id)
    if img is None:
        raise AppError("IMAGE_NOT_FOUND", "Image introuvable.", status_code=404)
    path = _image_path(img)
    if not path.is_file():
        raise AppError("IMAGE_FILE_MISSING", "Fichier image absent du disque.", status_code=404)
    return FileResponse(path, media_type="image/jpeg", filename=img.filename)


@router.delete("/images/{image_id}", status_code=204)
def delete_image(image_id: str, db: Session = Depends(get_db)) -> None:
    img = db.get(ExtractedImage, image_id)
    if img is None:
        raise AppError("IMAGE_NOT_FOUND", "Image introuvable.", status_code=404)
    path = _image_path(img)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(img)
    db.commit()
