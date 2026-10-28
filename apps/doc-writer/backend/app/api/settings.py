"""Routes /api/v1/settings — Mistral runtime config + test connexion."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.demo_mode import get_demo_enabled, set_demo_enabled
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
from app.core.prompts import PROMPT_KEYS, get_all_prompts, set_prompt
from app.db.session import get_db
from app.schemas import (
    ApiTestResult,
    PromptEntryOut,
    PromptsIn,
    PromptsOut,
    SettingsIn,
    SettingsOut,
    TestConnectionOut,
)


log = logging.getLogger("doc_writer.settings")

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)) -> SettingsOut:
    s = get_effective_settings(db)
    return SettingsOut(
        api_key_set=bool(s["api_key"]),
        base_url=s["base_url"],
        chat_model=s["chat_model"],
        embed_model=s["embed_model"],
        vision_model=s["vision_model"],
        ocr_model=s["ocr_model"],
        transcribe_model=s["transcribe_model"],
        voxtral_api_key_set=bool(s["voxtral_api_key"]),
        voxtral_base_url=s["voxtral_base_url"],
        llm_enabled=get_llm_enabled(db),
        llm_tested=get_llm_tested(db),
        demo_enabled=get_demo_enabled(db),
    )


@router.post("", response_model=SettingsOut)
def write_settings(payload: SettingsIn, db: Session = Depends(get_db)) -> SettingsOut:
    save_settings(db, payload.model_dump(exclude_unset=True))
    if payload.llm_enabled is not None:
        set_llm_enabled(db, payload.llm_enabled)
    if payload.demo_enabled is not None:
        set_demo_enabled(db, payload.demo_enabled)
    s = get_effective_settings(db)
    return SettingsOut(
        api_key_set=bool(s["api_key"]),
        base_url=s["base_url"],
        chat_model=s["chat_model"],
        embed_model=s["embed_model"],
        vision_model=s["vision_model"],
        ocr_model=s["ocr_model"],
        transcribe_model=s["transcribe_model"],
        voxtral_api_key_set=bool(s["voxtral_api_key"]),
        voxtral_base_url=s["voxtral_base_url"],
        llm_enabled=get_llm_enabled(db),
        llm_tested=get_llm_tested(db),
        demo_enabled=get_demo_enabled(db),
    )


@router.post("/test", response_model=TestConnectionOut)
def test_connection(db: Session = Depends(get_db)) -> TestConnectionOut:
    """Teste CHAQUE API appelee et renvoie une liste de modeles PAR API.

    - API Mistral principale (chat/embed/vision/ocr) : pilote le badge LLM et
      `llm_tested` (compat — expose aussi via `ok`/`models`/`error`).
    - API Voxtral dediee (transcription) : testee separement UNIQUEMENT si une
      cle dediee est configuree ; son echec n'affecte pas le badge principal.
    """
    if not get_llm_enabled(db):
        return TestConnectionOut(ok=False, error="LLM desactive")
    try:
        client = MistralClient.from_db(db)
    except MistralError as e:
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, error=str(e))

    apis: list[ApiTestResult] = []

    # 1) API Mistral principale -> etat du badge / llm_tested.
    try:
        main = ApiTestResult(
            api="mistral", base_url=client.base_url, ok=True, models=client.list_models()
        )
    except Exception as e:  # noqa: BLE001
        log.exception("test connection (mistral) failed")
        main = ApiTestResult(
            api="mistral", base_url=client.base_url, ok=False, error=f"{type(e).__name__}: {e}"
        )
    apis.append(main)
    set_llm_tested(db, main.ok)

    # 2) API Voxtral dediee (transcription), seulement si une cle propre existe.
    if client.transcribe_dedicated:
        try:
            apis.append(
                ApiTestResult(
                    api="voxtral",
                    base_url=client.transcribe_base_url,
                    ok=True,
                    models=client.list_transcribe_models(),
                )
            )
        except Exception as e:  # noqa: BLE001
            log.exception("test connection (voxtral) failed")
            apis.append(
                ApiTestResult(
                    api="voxtral",
                    base_url=client.transcribe_base_url,
                    ok=False,
                    error=f"{type(e).__name__}: {e}",
                )
            )

    return TestConnectionOut(ok=main.ok, models=main.models, error=main.error, apis=apis)


# ---- Prompts LLM editables runtime ----------------------------------------


def _prompts_to_out(db: Session) -> PromptsOut:
    raw = get_all_prompts(db)
    return PromptsOut(
        pptx_analysis=PromptEntryOut(**raw["pptx_analysis"]),  # type: ignore[arg-type]
        pptx_fill=PromptEntryOut(**raw["pptx_fill"]),  # type: ignore[arg-type]
    )


@router.get("/prompts", response_model=PromptsOut)
def read_prompts(db: Session = Depends(get_db)) -> PromptsOut:
    """Renvoie les 2 prompts edites par l'utilisateur, avec `is_default=True`
    si la cle est absente de la DB (le defaut hardcode est renvoye dans `value`)."""
    return _prompts_to_out(db)


@router.post("/prompts", response_model=PromptsOut)
def write_prompts(
    payload: PromptsIn,
    db: Session = Depends(get_db),
) -> PromptsOut:
    """Met a jour les prompts. Chaine vide '' = reset au defaut (efface la
    cle DB). Champ omis (None) = pas de changement."""
    data = payload.model_dump(exclude_unset=True)
    for name in PROMPT_KEYS:
        if name in data and data[name] is not None:
            set_prompt(db, name, data[name])
    return _prompts_to_out(db)
