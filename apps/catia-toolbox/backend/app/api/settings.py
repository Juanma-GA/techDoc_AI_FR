"""Routes /api/v1/settings - chemins OneDrive et configuration Composer."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import composer_converter, composer_license, onedrive
from app.db.session import get_db
from app.schemas import SettingsIn, SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_out(db: Session) -> SettingsOut:
    roots = onedrive.get_onedrive_roots(db)
    return SettingsOut(
        onedrive_input_root=roots["input"],
        onedrive_output_root=roots["output"],
        composer_license_server=composer_license.get_license_server(db),
        composer_converter_path=composer_converter.get_converter_path(db),
        composer_settings_path=composer_converter.get_settings_path(db),
    )


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return _settings_out(db)


@router.post("", response_model=SettingsOut)
def write_settings(payload: SettingsIn, db: Session = Depends(get_db)) -> SettingsOut:
    if payload.onedrive_input_root is not None or payload.onedrive_output_root is not None:
        onedrive.set_onedrive_roots(
            db,
            input_root=payload.onedrive_input_root,
            output_root=payload.onedrive_output_root,
        )
    if payload.composer_license_server is not None:
        composer_license.set_license_server(db, payload.composer_license_server)
    if payload.composer_converter_path is not None or payload.composer_settings_path is not None:
        composer_converter.set_paths(
            db,
            executable=payload.composer_converter_path,
            settings_file=payload.composer_settings_path,
        )
    return _settings_out(db)
