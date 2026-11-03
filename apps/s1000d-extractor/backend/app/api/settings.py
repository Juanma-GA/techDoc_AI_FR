"""Routes /api/v1/settings - runtime mode configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.demo_mode import get_demo_enabled, set_demo_enabled
from app.db.session import get_control_db
from app.schemas import SettingsIn, SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_out(control_db: Session) -> SettingsOut:
    return SettingsOut(demo_enabled=get_demo_enabled(control_db))


@router.get("", response_model=SettingsOut)
def read_settings(
    control_db: Session = Depends(get_control_db),
) -> SettingsOut:
    return _settings_out(control_db)


@router.post("", response_model=SettingsOut)
def write_settings(
    payload: SettingsIn,
    control_db: Session = Depends(get_control_db),
) -> SettingsOut:
    if payload.demo_enabled is not None:
        set_demo_enabled(control_db, payload.demo_enabled)
    return _settings_out(control_db)
