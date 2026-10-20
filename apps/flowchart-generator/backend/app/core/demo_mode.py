"""Persistence for the normal/demo application mode preference."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import AppConfig

DEMO_MODE_KEY = "demo_enabled"


def get_demo_enabled(db: Session) -> bool:
    try:
        row = db.get(AppConfig, DEMO_MODE_KEY)
        return row is not None and row.value.strip().lower() in {"1", "true", "yes"}
    except SQLAlchemyError:
        db.rollback()
        return False


def set_demo_enabled(db: Session, enabled: bool) -> None:
    value = "true" if enabled else "false"
    row = db.get(AppConfig, DEMO_MODE_KEY)
    if row is None:
        db.add(AppConfig(key=DEMO_MODE_KEY, value=value))
    else:
        row.value = value
    db.commit()
