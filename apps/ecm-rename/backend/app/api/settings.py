"""Routes /api/v1/settings - Mistral runtime config + test connexion."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.mistral_client import (
    MistralClient,
    MistralError,
    get_effective_settings,
    get_llm_enabled,
    get_llm_tested,
    save_settings,
    set_llm_enabled,
    set_llm_tested,
)
from app.db.session import get_db
from app.schemas import SettingsIn, SettingsOut, TestConnectionOut


log = logging.getLogger("ecm_rename.settings")

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_out(db: Session) -> SettingsOut:
    s = get_effective_settings(db)
    return SettingsOut(
        api_key_set=bool(s["api_key"]),
        base_url=s["base_url"],
        chat_model=s["chat_model"],
        embed_model=s["embed_model"],
        llm_enabled=get_llm_enabled(db),
        llm_tested=get_llm_tested(db),
    )


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return _settings_out(db)


@router.post("", response_model=SettingsOut)
def write_settings(payload: SettingsIn, db: Session = Depends(get_db)) -> SettingsOut:
    save_settings(db, payload.model_dump(exclude_unset=True))
    if payload.llm_enabled is not None:
        set_llm_enabled(db, payload.llm_enabled)
    return _settings_out(db)


@router.post("/test", response_model=TestConnectionOut)
def test_connection(db: Session = Depends(get_db)) -> TestConnectionOut:
    if not get_llm_enabled(db):
        return TestConnectionOut(ok=False, error="LLM desactive")
    try:
        mistral = MistralClient.from_db(db)
    except MistralError as e:
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, error=str(e))
    try:
        models = mistral.list_models()
    except Exception as e:  # noqa: BLE001
        log.exception("test connection failed")
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, error=f"{type(e).__name__}: {e}")
    set_llm_tested(db, True)
    return TestConnectionOut(ok=True, models=models)
