"""GET/POST/PUT/DELETE /api/v1/projects[/{id}] — Sprint S0."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Project
from app.db.session import get_db
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate


router = APIRouter(tags=["projects"])


def _project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise AppError(
            code="PROJECT_NOT_FOUND",
            message="Projet introuvable",
            status_code=404,
            detail={"id": str(project_id)},
        )
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(
        name=body.name.strip(),
        description=body.description,
        vision_enabled=body.vision_enabled,
    )
    db.add(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            code="PROJECT_NAME_TAKEN",
            message="Un projet avec ce nom existe déjà",
            status_code=409,
            detail={"name": body.name},
        ) from exc
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> Project:
    return _project_or_404(db, project_id)


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
) -> Project:
    project = _project_or_404(db, project_id)

    if body.name is not None:
        project.name = body.name.strip()
    if body.description is not None:
        project.description = body.description
    if body.vision_enabled is not None:
        project.vision_enabled = body.vision_enabled

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            code="PROJECT_NAME_TAKEN",
            message="Un projet avec ce nom existe déjà",
            status_code=409,
            detail={"name": body.name},
        ) from exc
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    project = _project_or_404(db, project_id)
    db.delete(project)
    db.commit()
