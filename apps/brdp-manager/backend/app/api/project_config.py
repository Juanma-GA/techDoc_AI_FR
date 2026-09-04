"""Routes /api/v1/project-config - metadonnees S1000D du projet (ligne unique)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import ProjectConfig
from app.db.session import get_db
from app.schemas import ProjectConfigIn, ProjectConfigOut

router = APIRouter(prefix="/project-config", tags=["project-config"])


def _get_or_create(db: Session) -> ProjectConfig:
    row = db.get(ProjectConfig, 1)
    if row is None:
        row = ProjectConfig(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("", response_model=ProjectConfigOut)
def read_project_config(db: Session = Depends(get_db)) -> ProjectConfig:
    return _get_or_create(db)


@router.post("", response_model=ProjectConfigOut)
def write_project_config(payload: ProjectConfigIn, db: Session = Depends(get_db)) -> ProjectConfig:
    row = _get_or_create(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row
