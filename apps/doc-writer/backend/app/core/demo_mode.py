"""Persist the normal/demo mode preference in AppConfig."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AppConfig

DEMO_MODE_KEY = "demo_enabled"


def get_demo_enabled(db: Session) -> bool:
    row = db.get(AppConfig, DEMO_MODE_KEY)
    return row is not None and row.value.strip().lower() in {"1", "true", "yes"}


def set_demo_enabled(db: Session, enabled: bool) -> None:
    value = "true" if enabled else "false"
    row = db.get(AppConfig, DEMO_MODE_KEY)
    if row is None:
        db.add(AppConfig(key=DEMO_MODE_KEY, value=value))
    else:
        row.value = value
    db.commit()
