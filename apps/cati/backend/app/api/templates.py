"""Routes /api/v1/templates - gestion des templates Excel de sortie (UI)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, UploadFile
from openpyxl import load_workbook
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.core.security import read_and_validate, safe_storage_join
from app.core.templates import validate_template_xlsx
from app.db.models import CatiTemplate
from app.db.session import get_db
from app.schemas import TemplateOut

log = logging.getLogger("cati.templates")

router = APIRouter(prefix="/templates", tags=["templates"])

ALLOWED_EXTS = {".xlsx"}


def _templates_dir() -> Path:
    return safe_storage_join(Path(settings.storage_dir), "templates")


def _header_columns(path: str, sheet_name: str) -> list[str]:
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception:  # noqa: BLE001
        return []
    try:
        if sheet_name not in wb.sheetnames:
            return []
        ws = wb[sheet_name]
        row = next(ws.iter_rows(max_row=1), [])
        return [str(c.value).strip() for c in row if c.value is not None and str(c.value).strip()]
    finally:
        wb.close()


def _template_out(tpl: CatiTemplate) -> TemplateOut:
    return TemplateOut(
        id=tpl.id,
        name=tpl.name,
        filename=tpl.filename,
        sheet_name=tpl.sheet_name,
        header_row=tpl.header_row,
        data_start_row=tpl.data_start_row,
        is_default=tpl.is_default,
        header_columns=_header_columns(tpl.storage_path, tpl.sheet_name),
        created_at=tpl.created_at.isoformat() if tpl.created_at else "",
    )


def _get_template(db: Session, tpl_id: str) -> CatiTemplate:
    tpl = db.get(CatiTemplate, tpl_id)
    if tpl is None:
        raise AppError("TEMPLATE_NOT_FOUND", "Template introuvable.", status_code=404)
    return tpl


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)) -> list[TemplateOut]:
    rows = db.scalars(select(CatiTemplate).order_by(CatiTemplate.created_at.desc())).all()
    return [_template_out(t) for t in rows]


@router.post("", response_model=TemplateOut)
def upload_template(
    file: UploadFile,
    name: str = Form(""),
    sheet_name: str = Form("Catalogue"),
    header_row: int = Form(1),
    data_start_row: int = Form(2),
    db: Session = Depends(get_db),
) -> TemplateOut:
    raw, safe_name, _ext = read_and_validate(
        file, max_size=settings.max_upload_size_bytes, allowed_exts=ALLOWED_EXTS
    )

    tpl = CatiTemplate(
        name=(name.strip() or safe_name),
        filename=safe_name,
        sheet_name=sheet_name,
        header_row=header_row,
        data_start_row=data_start_row,
    )
    db.add(tpl)
    db.flush()

    target_dir = _templates_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"tpl_{tpl.id}.xlsx"
    path.write_bytes(raw)
    tpl.storage_path = str(path)

    # Validation : feuille attendue presente. Si KO -> on nettoie et on refuse.
    try:
        validate_template_xlsx(str(path), sheet_name)
    except AppError:
        path.unlink(missing_ok=True)
        db.rollback()
        raise

    # Premier template -> defaut d'office.
    if db.scalar(select(CatiTemplate).where(CatiTemplate.is_default.is_(True))) is None:
        tpl.is_default = True
    db.commit()
    return _template_out(tpl)


@router.post("/{tpl_id}/default", response_model=TemplateOut)
def set_default(tpl_id: str, db: Session = Depends(get_db)) -> TemplateOut:
    tpl = _get_template(db, tpl_id)
    db.execute(update(CatiTemplate).values(is_default=False))
    tpl.is_default = True
    db.commit()
    return _template_out(tpl)


@router.delete("/{tpl_id}", response_model=TemplateOut)
def delete_template(tpl_id: str, db: Session = Depends(get_db)) -> TemplateOut:
    tpl = _get_template(db, tpl_id)
    out = _template_out(tpl)
    was_default = tpl.is_default
    if tpl.storage_path:
        try:
            Path(tpl.storage_path).unlink(missing_ok=True)
        except OSError:
            log.warning("could not remove template file %s", tpl.storage_path)
    db.delete(tpl)
    db.flush()
    # Si on supprime le defaut, en promouvoir un autre.
    if was_default:
        nxt = db.scalar(select(CatiTemplate).order_by(CatiTemplate.created_at.desc()))
        if nxt is not None:
            nxt.is_default = True
    db.commit()
    return out


@router.post("/reset", tags=["templates"])
def reset_templates(db: Session = Depends(get_db)) -> dict[str, int]:
    """Purge tous les templates (fichiers + lignes). Best-effort."""
    rows = db.scalars(select(CatiTemplate)).all()
    n = len(rows)
    for tpl in rows:
        if tpl.storage_path:
            try:
                Path(tpl.storage_path).unlink(missing_ok=True)
            except OSError:
                pass
    db.query(CatiTemplate).delete()
    db.commit()
    return {"deleted": n}
