"""Routes /api/v1/settings - Mistral runtime config + test connexion."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.mistral_client import (
    MistralClient,
    MistralError,
    get_effective_settings,
    save_settings,
)
from app.db.session import get_db
from app.schemas import SettingsIn, SettingsOut, TestConnectionOut


log = logging.getLogger("template.settings")

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)) -> SettingsOut:
    s = get_effective_settings(db)
    return SettingsOut(
        api_key_set=bool(s["api_key"]),
        base_url=s["base_url"],
        chat_model=s["chat_model"],
        embed_model=s["embed_model"],
    )


@router.post("", response_model=SettingsOut)
def write_settings(payload: SettingsIn, db: Session = Depends(get_db)) -> SettingsOut:
    save_settings(db, payload.model_dump(exclude_unset=True))
    s = get_effective_settings(db)
    return SettingsOut(
        api_key_set=bool(s["api_key"]),
        base_url=s["base_url"],
        chat_model=s["chat_model"],
        embed_model=s["embed_model"],
    )


@router.post("/test", response_model=TestConnectionOut)
def test_connection(db: Session = Depends(get_db)) -> TestConnectionOut:
    try:
        mistral = MistralClient.from_db(db)
    except MistralError as e:
        return TestConnectionOut(ok=False, error=str(e))
    try:
        models = mistral.list_models()
    except Exception as e:  # noqa: BLE001
        log.exception("test connection failed")
        return TestConnectionOut(ok=False, error=f"{type(e).__name__}: {e}")
    return TestConnectionOut(ok=True, models=models)
