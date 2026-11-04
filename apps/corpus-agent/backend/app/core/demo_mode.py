"""Persistence for the normal/demo application mode preference."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.db.models import AppConfig, Project

DEMO_MODE_KEY = "demo_enabled"
DEMO_FOLDER_KEY = "demo_corpus_path"


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
        if project is not None:
            folder = db.get(AppConfig, DEMO_FOLDER_KEY)
            if folder is None:
                db.add(AppConfig(key=DEMO_FOLDER_KEY, value=project.corpus_path or ""))
            else:
                folder.value = project.corpus_path or ""
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
