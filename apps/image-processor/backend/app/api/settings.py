"""Routes for the persisted local application settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.demo_mode import get_demo_enabled, set_demo_enabled
from app.db.session import get_db
from app.schemas import SettingsIn, SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_out(db: Session) -> SettingsOut:
    return SettingsOut(demo_enabled=get_demo_enabled(db))


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return _settings_out(db)


@router.post("", response_model=SettingsOut)
def write_settings(payload: SettingsIn, db: Session = Depends(get_db)) -> SettingsOut:
    if payload.demo_enabled is not None:
        set_demo_enabled(db, payload.demo_enabled)
    return _settings_out(db)
