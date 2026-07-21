"""Routes /api/v1/templates - definitions de table REUTILISABLES (colonnes + regles)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import TableTemplate
from app.db.session import get_db
from app.schemas import TemplateIn, TemplateOut

router = APIRouter(prefix="/templates", tags=["templates"])


def _out(t: TableTemplate) -> TemplateOut:
    return TemplateOut(
        id=t.id,
        name=t.name,
        description=t.description or "",
        columns=t.columns or [],
        created_at=t.created_at,
    )


def _load(db: Session, template_id: str) -> TableTemplate:
    t = db.get(TableTemplate, template_id)
    if t is None:
        raise AppError("TEMPLATE_NOT_FOUND", "Modele introuvable.", status_code=404)
    return t


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)) -> list[TemplateOut]:
    rows = db.scalars(select(TableTemplate).order_by(TableTemplate.created_at.desc())).all()
    return [_out(t) for t in rows]


@router.post("", response_model=TemplateOut)
def create_template(payload: TemplateIn, db: Session = Depends(get_db)) -> TemplateOut:
    t = TableTemplate(
        name=payload.name.strip(),
        description=payload.description.strip(),
        columns=[c.model_dump() for c in payload.columns],
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _out(t)


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: str, db: Session = Depends(get_db)) -> TemplateOut:
    return _out(_load(db, template_id))


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: str, payload: TemplateIn, db: Session = Depends(get_db)
) -> TemplateOut:
    t = _load(db, template_id)
    t.name = payload.name.strip()
    t.description = payload.description.strip()
    t.columns = [c.model_dump() for c in payload.columns]
    db.commit()
    db.refresh(t)
    return _out(t)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, db: Session = Depends(get_db)) -> None:
    db.delete(_load(db, template_id))
    db.commit()
