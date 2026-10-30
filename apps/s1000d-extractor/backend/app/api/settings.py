"""Routes /api/v1/settings - Mistral runtime config + test connexion."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.demo_mode import get_demo_enabled, is_demo_mode, set_demo_enabled
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
from app.db.session import get_control_db, get_db, open_session
from app.schemas import SettingsIn, SettingsOut, TestConnectionOut

log = logging.getLogger("template.settings")

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_out(db: Session, control_db: Session) -> SettingsOut:
    s = get_effective_settings(db)
    return SettingsOut(
        api_key_set=bool(s["api_key"]),
        base_url=s["base_url"],
        chat_model=s["chat_model"],
        embed_model=s["embed_model"],
        llm_enabled=get_llm_enabled(db),
        llm_tested=get_llm_tested(db),
        demo_enabled=get_demo_enabled(control_db),
    )


@router.get("", response_model=SettingsOut)
def read_settings(
    db: Session = Depends(get_db), control_db: Session = Depends(get_control_db),
) -> SettingsOut:
    return _settings_out(db, control_db)


@router.post("", response_model=SettingsOut)
def write_settings(
    payload: SettingsIn,
    db: Session = Depends(get_db),
    control_db: Session = Depends(get_control_db),
) -> SettingsOut:
    current_mode = is_demo_mode(db)
    target_mode = payload.demo_enabled if payload.demo_enabled is not None else current_mode
    settings_db = db if target_mode == current_mode else open_session(target_mode)
    try:
        save_settings(settings_db, payload.model_dump(exclude_unset=True, exclude={"demo_enabled"}))
        if payload.llm_enabled is not None:
            set_llm_enabled(settings_db, payload.llm_enabled)
        if payload.demo_enabled is not None:
            set_demo_enabled(control_db, payload.demo_enabled)
        return _settings_out(settings_db, control_db)
    finally:
        if settings_db is not db:
            settings_db.close()


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
    except Exception as e:
        log.exception("test connection failed")
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, error=f"{type(e).__name__}: {e}")
    set_llm_tested(db, True)
    return TestConnectionOut(ok=True, models=models)
