"""GET/POST /api/v1/settings/mistral + POST /settings/mistral/test."""

import structlog
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.core.mistral_settings import (
    get_ai_custom_prompt,
    get_checklist_ai_scan,
    get_checklist_context,
    get_effective,
    get_endpoint,
    get_feedback_enabled,
    get_llm_enabled,
    get_llm_max_calls,
    get_llm_tested,
    get_verify_enabled,
    get_verify_passes,
    get_vision_enabled,
    is_secret_unreadable,
    save,
    set_ai_custom_prompt,
    set_checklist_ai_scan,
    set_checklist_context,
    set_feedback_enabled,
    set_llm_enabled,
    set_llm_max_calls,
    set_llm_tested,
    set_verify_enabled,
    set_verify_passes,
    set_vision_enabled,
)
from app.core.encryption import EncryptionError
from app.core.errors import AppError
from app.core.security import MISTRAL_URL_NOT_ALLOWED_MESSAGE, validate_mistral_base_url
from app.db.session import get_db
from app.schemas import (
    ChecklistContextIn,
    ChecklistContextOut,
    MistralSettingsIn,
    MistralSettingsOut,
    TestConnectionOut,
)

# Inject the OS trust store into Python's ssl module so corporate CAs and
# transparent SSL proxies work without `pip install certifi --upgrade` games.
# Idempotent + best-effort: silently skip if the package is missing or the
# runtime doesn't support it.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass


logger = structlog.get_logger(__name__)


router = APIRouter(prefix="/settings", tags=["settings"])


def _build_out(db: Session) -> MistralSettingsOut:
    s = get_effective(db)
    key = s["api_key"] or ""
    preview = (key[:4] + "…" + key[-4:]) if len(key) > 10 else ("•" * len(key) if key else "")
    return MistralSettingsOut(
        api_key_set=bool(key),
        api_key_preview=preview,
        api_key_unreadable=is_secret_unreadable(db, "api_key"),
        base_url=s["base_url"],
        chat_model=s["chat_model"],
        vision_model=s.get("vision_model", "mistral-medium-3-5"),
        vision_enabled=get_vision_enabled(db),
        llm_enabled=get_llm_enabled(db),
        llm_tested=get_llm_tested(db),
        checklist_ai_scan=get_checklist_ai_scan(db),
    )


@router.get("/mistral", response_model=MistralSettingsOut)
def get_mistral_settings(db: Session = Depends(get_db)) -> MistralSettingsOut:
    return _build_out(db)


@router.post("/mistral", response_model=MistralSettingsOut)
def update_mistral_settings(
    body: MistralSettingsIn,
    db: Session = Depends(get_db),
) -> MistralSettingsOut:
    # `exclude_unset` : ne retient QUE les champs explicitement envoyes par le
    # client. Un `model_dump()` plat inclurait aussi les champs absents du
    # payload avec leur valeur par defaut Pydantic (ex. `base_url` retombe a
    # "https://api.mistral.ai") et les ecraserait en base — un update partiel
    # comme `{chat_model: "..."}` (choix d'un modele dans la liste du test)
    # effacait alors silencieusement le base_url/vision_model deja configures.
    payload = body.model_dump(exclude_unset=True)
    # Empty api_key in the request means "keep the current one".
    if not payload.get("api_key"):
        payload.pop("api_key", None)
    if "base_url" in payload:
        try:
            payload["base_url"] = validate_mistral_base_url(payload["base_url"])
        except ValueError as exc:
            raise AppError(
                "MISTRAL_URL_NOT_ALLOWED",
                MISTRAL_URL_NOT_ALLOWED_MESSAGE,
                status_code=422,
            ) from exc
    # `vision_enabled` is stored separately (boolean flag, not in Mistral
    # client config). Pop it before delegating to `save()`.
    vision_enabled = payload.pop("vision_enabled", None)
    llm_enabled = payload.pop("llm_enabled", None)
    checklist_ai_scan = payload.pop("checklist_ai_scan", None)
    try:
        save(db, payload)
    except EncryptionError as exc:
        db.rollback()
        raise AppError(
            "MISTRAL_KEY_ENCRYPTION_REQUIRED",
            "Configurez une clé Fernet valide avant d'enregistrer une clé Mistral.",
            status_code=503,
        ) from exc
    if vision_enabled is not None:
        set_vision_enabled(db, bool(vision_enabled))
    if llm_enabled is not None:
        set_llm_enabled(db, bool(llm_enabled))
    if checklist_ai_scan is not None:
        set_checklist_ai_scan(db, bool(checklist_ai_scan))
    return _build_out(db)


class VisionToggleIn(BaseModel):
    enabled: bool


@router.post("/vision")
def toggle_vision(body: VisionToggleIn, db: Session = Depends(get_db)) -> dict:
    """Standalone endpoint to toggle the vision pipeline without
    re-sending the whole Mistral payload."""
    set_vision_enabled(db, body.enabled)
    return {"enabled": get_vision_enabled(db)}


@router.post("/mistral/test", response_model=TestConnectionOut)
def test_mistral_connection(db: Session = Depends(get_db)) -> TestConnectionOut:
    if not get_llm_enabled(db):
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, message="LLM desactive", models=[])
    s = get_effective(db)
    if not s["api_key"]:
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, message="Aucune clé API configurée.", models=[])
    try:
        s = get_endpoint(db)
    except AppError as exc:
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, message=exc.message, models=[])
    base_url = s["base_url"]
    try:
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            r = client.get(
                f"{base_url}/v1/models",
                headers={"Authorization": f"Bearer {s['api_key']}"},
            )
        if r.status_code != 200:
            set_llm_tested(db, False)
            return TestConnectionOut(
                ok=False,
                message=f"HTTP {r.status_code}",
                models=[],
            )
        data = r.json() or {}
        ids = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
        set_llm_tested(db, True)
        return TestConnectionOut(
            ok=True,
            message=f"{len(ids)} modèle(s) accessible(s).",
            models=ids[:50],
        )
    except ValueError:
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, message=MISTRAL_URL_NOT_ALLOWED_MESSAGE, models=[])
    except Exception as exc:  # noqa: BLE001
        # Catch broad — Mistral test must never raise a 500 to the UI; any
        # network/SSL/proxy/parsing problem is reported as `ok=false`.
        logger.warning("mistral_test_failed", error=type(exc).__name__)
        set_llm_tested(db, False)
        return TestConnectionOut(
            ok=False,
            message=f"Échec du test de connexion ({type(exc).__name__}).",
            models=[],
        )


# ---- AI free-text guidelines ---------------------------------------------


class AiPromptIn(BaseModel):
    prompt: str = ""


@router.get("/ai-prompt")
def get_ai_prompt(db: Session = Depends(get_db)) -> dict:
    return {"prompt": get_ai_custom_prompt(db)}


@router.post("/ai-prompt")
def update_ai_prompt(body: AiPromptIn, db: Session = Depends(get_db)) -> dict:
    set_ai_custom_prompt(db, body.prompt)
    return {"prompt": get_ai_custom_prompt(db)}


@router.get("/checklist-context", response_model=ChecklistContextOut)
def get_checklist_context_settings(db: Session = Depends(get_db)) -> ChecklistContextOut:
    return ChecklistContextOut(**get_checklist_context(db))


@router.post("/checklist-context", response_model=ChecklistContextOut)
def update_checklist_context(
    body: ChecklistContextIn,
    db: Session = Depends(get_db),
) -> ChecklistContextOut:
    current = get_checklist_context(db)
    current.update(body.model_dump(exclude_unset=True))
    set_checklist_context(db, current)
    return ChecklistContextOut(**get_checklist_context(db))


# ---- Fiabilisation LLM ----------------------------------------------------
# Pilote la verification adversariale (refuteur, vote majoritaire) + le
# feedback global des rejets + le budget d'appels. cf. core/verifier.py,
# core/feedback.py, core/llm_budget.py.


class ReliabilityOut(BaseModel):
    verify_enabled: bool
    verify_passes: int
    max_calls: int
    feedback_enabled: bool


class ReliabilityIn(BaseModel):
    verify_enabled: bool | None = None
    verify_passes: int | None = None
    max_calls: int | None = None
    feedback_enabled: bool | None = None


def _reliability_out(db: Session) -> ReliabilityOut:
    return ReliabilityOut(
        verify_enabled=get_verify_enabled(db),
        verify_passes=get_verify_passes(db),
        max_calls=get_llm_max_calls(db),
        feedback_enabled=get_feedback_enabled(db),
    )


@router.get("/reliability", response_model=ReliabilityOut)
def get_reliability(db: Session = Depends(get_db)) -> ReliabilityOut:
    return _reliability_out(db)


@router.post("/reliability", response_model=ReliabilityOut)
def update_reliability(body: ReliabilityIn, db: Session = Depends(get_db)) -> ReliabilityOut:
    if body.verify_enabled is not None:
        set_verify_enabled(db, body.verify_enabled)
    if body.verify_passes is not None:
        set_verify_passes(db, body.verify_passes)
    if body.max_calls is not None:
        set_llm_max_calls(db, body.max_calls)
    if body.feedback_enabled is not None:
        set_feedback_enabled(db, body.feedback_enabled)
    return _reliability_out(db)
