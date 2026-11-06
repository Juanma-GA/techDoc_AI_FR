"""Persistence for the normal/demo application mode preference."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.config import settings
from app.db.models import AppConfig, Project

DEMO_MODE_KEY = "demo_enabled"
DEMO_FOLDER_KEY = "demo_corpus_path"


def demo_folder_path(project_id: uuid.UUID) -> Path:
    return Path(settings.storage_dir) / f"project_{project_id}" / "connected-folder"


def is_embedded_demo_folder(project_id: uuid.UUID, path: str | None) -> bool:
    if not path:
        return False
    try:
        return Path(path).resolve() == demo_folder_path(project_id).resolve()
    except OSError:
        return False


def remember_demo_folder(db: Session, path: str) -> None:
    row = db.get(AppConfig, DEMO_FOLDER_KEY)
    if row is None:
        db.add(AppConfig(key=DEMO_FOLDER_KEY, value=path))
    else:
        row.value = path


def demo_project_filter() -> ColumnElement[bool]:
    from app.core.demo_seed import DEMO_PROJECT_DESCRIPTION, DEMO_PROJECT_NAME

    return or_(Project.name == DEMO_PROJECT_NAME, Project.description == DEMO_PROJECT_DESCRIPTION)


def get_demo_enabled(db: Session) -> bool:
    try:
        row = db.get(AppConfig, DEMO_MODE_KEY)
        return row is not None and row.value.strip().lower() in {"1", "true", "yes"}
    except SQLAlchemyError:
        db.rollback()
        return False


def set_demo_enabled(db: Session, enabled: bool) -> None:
    if not enabled and get_demo_enabled(db):
        project = db.scalar(select(Project).where(demo_project_filter()))
        if project is not None and not is_embedded_demo_folder(project.id, project.corpus_path):
            remember_demo_folder(db, project.corpus_path or "")
    value = "true" if enabled else "false"
    row = db.get(AppConfig, DEMO_MODE_KEY)
    if row is None:
        db.add(AppConfig(key=DEMO_MODE_KEY, value=value))
    else:
        row.value = value
    db.commit()


def visible_projects(db: Session, project_ids: list[uuid.UUID] | None = None) -> list[Project]:
    """Keep normal projects stored, but expose only the seeded project in demo."""
    statement = select(Project).order_by(Project.created_at.desc())
    if get_demo_enabled(db):
        statement = statement.where(demo_project_filter())
    else:
        statement = statement.where(~demo_project_filter())
    if project_ids is not None:
        statement = statement.where(Project.id.in_(project_ids))
    return list(db.scalars(statement))
