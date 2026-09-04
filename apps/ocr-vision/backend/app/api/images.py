"""Routes images/illustrations extraites : liste, service du fichier, suppression."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.db.models import ExtractedImage, Project, ProjectTable
from app.db.session import get_db
from app.schemas import ImageOut, ImagesExportIn, ImagesExportOut

router = APIRouter(tags=["images"])

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _slug(name: str) -> str:
    s = _SAFE.sub("_", (name or "").strip()).strip("._")
    return s or "table"


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


@router.post("/images/export", response_model=ImagesExportOut)
def export_images(payload: ImagesExportIn, db: Session = Depends(get_db)) -> ImagesExportOut:
    """Copie les images d'une table vers un sous-dossier du repertoire cible.

    Ecart local-first documente (comme l'export CSV/XLSX) : ecrit sur un chemin
    disque arbitraire fourni par l'utilisateur. Garde-fous : dossier cible
    existant, noms de fichiers controles, anti-traversee.
    """
    table = db.get(ProjectTable, payload.project_table_id)
    if table is None:
        raise AppError("TABLE_NOT_FOUND", "Table introuvable.", status_code=404)
    project = db.get(Project, table.project_id)

    target = Path(payload.target_dir).expanduser()
    if not target.exists() or not target.is_dir():
        raise AppError(
            "TARGET_DIR_INVALID",
            f"Repertoire cible introuvable : {payload.target_dir}",
            status_code=400,
        )

    project_name = project.name if project else "projet"
    dest_dir = (target / f"{_slug(project_name)}__{_slug(table.name)}_images").resolve()
    # Garde-fou anti-traversee : le sous-dossier doit rester sous la cible.
    if target.resolve() not in dest_dir.parents:
        raise AppError("TARGET_DIR_INVALID", "Chemin de sortie invalide.", status_code=400)

    imgs = db.scalars(
        select(ExtractedImage)
        .where(ExtractedImage.project_table_id == table.id)
        .order_by(ExtractedImage.created_at.asc())
    ).all()

    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for img in imgs:
        src = _image_path(img)
        if src.is_file():
            shutil.copy2(src, dest_dir / img.filename)
            count += 1
    return ImagesExportOut(path=str(dest_dir), count=count)


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
