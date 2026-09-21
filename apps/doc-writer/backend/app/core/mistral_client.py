"""Client Mistral minimal — httpx async (streaming) + httpx sync (embeddings).

Pas de SDK Mistral. La configuration runtime est lue dans la table `app_config`
avec fallback sur `app.config.settings` (qui lit le `.env`).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AppConfig

logger = logging.getLogger(__name__)


try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass


CONFIG_KEYS = {
    "api_key": "MISTRAL_API_KEY",
    "base_url": "MISTRAL_BASE_URL",
    "chat_model": "MISTRAL_CHAT_MODEL",
    "embed_model": "MISTRAL_EMBED_MODEL",
    "vision_model": "MISTRAL_VISION_MODEL",
    "ocr_model": "MISTRAL_OCR_MODEL",
    "transcribe_model": "MISTRAL_TRANSCRIBE_MODEL",
    # Cle/endpoint DEDIES a la transcription Voxtral (optionnel). Vides -> repli
    # sur la cle/URL Mistral principale (cf. MistralClient.from_db).
    "voxtral_api_key": "VOXTRAL_API_KEY",
    "voxtral_base_url": "VOXTRAL_BASE_URL",
}

DEFAULT_TRANSCRIBE_MODEL = "voxtral-mini-latest"
REALTIME_TRANSCRIBE_MODEL = "voxtral-mini-transcribe-realtime-2602"
_LEGACY_TRANSCRIBE_MODELS = {
    "voxtral-mini-transcribe-26-02",
    "voxtral-mini-transcribe-realtime-2602",
}

# Cles dont la valeur est chiffree au repos dans AppConfig (cf. encryption.py).
# Secrets sensibles uniquement ; flags, modeles et URLs restent en clair.
ENCRYPTED_KEYS = {"MISTRAL_API_KEY", "VOXTRAL_API_KEY"}

# Interrupteur global LLM (standard). Cle bare dans `app_config`, defaut "true".
# OFF = on saute la tache confiee a l'IA (fallback gracieux), la cle Mistral est conservee.
LLM_ENABLED_KEY = "llm_enabled"

# Dernier test de connexion Mistral reussi ? (standard). Cle bare dans
# `app_config`, defaut "false". Le badge LLM ne passe au vert (ON) que si la cle
# est configuree, le LLM active ET ce flag vrai. Remis a "false" des que la cle
# ou la base_url change (re-test obligatoire).
LLM_TESTED_KEY = "llm_last_test_ok"


class MistralError(RuntimeError):
    """Levée si Mistral n'est pas configuré ou rejette un appel."""


# Noms de langue pour les consignes de traduction (cle = code session).
_LANG_NAMES = {"fr": "French", "en": "English", "es": "Spanish"}


# Consigne de transcription vision (multimodal). Insiste sur l'interpretation
# du graphique : c'est la valeur ajoutee vs l'OCR texte (langues en drapeaux,
# niveaux en barres/points).
_VISION_PROMPT = (
    "Transcris INTEGRALEMENT le contenu de ce document (souvent un CV) en "
    "texte/markdown, fidelement et SANS rien resumer ni omettre. Inclus tout : "
    "identite, intitules de poste, experiences avec leurs DATES (mois/annees), "
    "formations et ecoles, competences, outils, et surtout les LANGUES avec "
    "leur NIVEAU. Quand une information est representee GRAPHIQUEMENT (barres, "
    "points, jauges, etoiles, drapeaux), INTERPRETE-la et ecris-la en clair "
    "(ex. 'Anglais : courant', 'Espagnol : intermediaire', '4/5'). Respecte "
    "l'ordre de lecture meme en multi-colonnes. Ne mets ni preambule ni "
    "commentaire : renvoie UNIQUEMENT le contenu transcrit."
)


def _normalize_base_url(url: str) -> str:
    """Ramene une URL Mistral (racine ou endpoint connu) a sa racine API."""
    normalized = url.rstrip("/")
    for suffix in ("/v1/audio/transcriptions", "/v1/models", "/v1"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _assert_base_url_allowed(url: str) -> None:
    """Bloque le routage IA vers un endpoint non-approuve (F-01, doc 159).

    Seuls les endpoints listes dans `settings.mistral_allowed_base_urls`
    (defaut : l'environnement Mistral enterprise approuve) peuvent recevoir
    du contenu de document. Comparaison sur la racine normalisee (insensible
    au suffixe /v1, / final, casse du host).
    """
    from app.config import settings

    if not url:
        return
    normalized = _normalize_base_url(url).lower()
    allowed = {_normalize_base_url(u).lower() for u in settings.mistral_allowed_base_urls}
    if normalized not in allowed:
        raise AppError(
            code="BASE_URL_NOT_ALLOWED",
            message=(
                "Endpoint IA non approuve. Seuls les endpoints de la liste "
                "autorisee (mistral_allowed_base_urls) peuvent recevoir du "
                "contenu de document."
            ),
            status_code=400,
            detail={"base_url": url, "allowed": sorted(allowed)},
        )


def _get_secret_manager():  # type: ignore[no-untyped-def]
    """SecretManager configure depuis settings.

    F-05 (hardening 2026-09-14) : ENCRYPTION_KEY absente (defaut tier1 local)
    ne degrade plus en clair. Une cle est auto-provisionnee a cote de la DB
    (gitignoree, cf. `load_or_create_local_key`) et reutilisee a chaque appel,
    de sorte que le secret Mistral soit TOUJOURS chiffre au repos, meme quand
    l'operateur n'a rien configure explicitement. Le repli en clair ne survient
    plus qu'en cas d'echec d'ecriture disque (filesystem read-only, etc.)."""
    from pathlib import Path

    from app.config import settings
    from app.core.encryption import SecretManager, load_or_create_local_key

    key = settings.encryption_key
    if not key:
        key_path = Path(settings.encryption_key_path)
        try:
            key = load_or_create_local_key(key_path)
        except OSError as e:
            logger.error("Local encryption key auto-provisioning failed (%s): %s", key_path, e)
            logger.warning("Encryption key not configured - secrets stored in plaintext (INSECURE)")
            return SecretManager(None)
    return SecretManager(key)


def _read_config(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppConfig, key)
    if not row or not row.value:
        return default
    if key in ENCRYPTED_KEYS:
        try:
            return _get_secret_manager().decrypt(row.value)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to decrypt %s: %s", key, e)
            return default
    return row.value


def _write_config(db: Session, key: str, value: str) -> None:
    if key in ENCRYPTED_KEYS and value:
        try:
            value = _get_secret_manager().encrypt(value)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to encrypt %s: %s", key, e)
            raise MistralError(f"Encryption failed: {e}") from e
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=value))
    else:
        row.value = value


def get_effective_settings(db: Session) -> dict[str, str]:
    from app.config import settings as defaults

    transcribe_model = _read_config(
        db, CONFIG_KEYS["transcribe_model"], defaults.mistral_transcribe_model
    )
    if transcribe_model in _LEGACY_TRANSCRIBE_MODELS:
        transcribe_model = DEFAULT_TRANSCRIBE_MODEL
    return {
        "api_key": _read_config(db, CONFIG_KEYS["api_key"], defaults.mistral_api_key),
        "base_url": _read_config(db, CONFIG_KEYS["base_url"], defaults.mistral_base_url),
        "chat_model": _read_config(db, CONFIG_KEYS["chat_model"], defaults.mistral_chat_model),
        "embed_model": _read_config(db, CONFIG_KEYS["embed_model"], defaults.mistral_embed_model),
        "vision_model": _read_config(
            db, CONFIG_KEYS["vision_model"], defaults.mistral_vision_model
        ),
        "ocr_model": _read_config(db, CONFIG_KEYS["ocr_model"], defaults.mistral_ocr_model),
        "transcribe_model": transcribe_model,
        "voxtral_api_key": _read_config(
            db, CONFIG_KEYS["voxtral_api_key"], defaults.voxtral_api_key
        ),
        "voxtral_base_url": _read_config(
            db, CONFIG_KEYS["voxtral_base_url"], defaults.voxtral_base_url
        ),
    }


def save_settings(db: Session, data: dict[str, Any]) -> None:
    if data.get("base_url"):
        _assert_base_url_allowed(str(data["base_url"]))
    invalidate_test = False
    for k, v in data.items():
        if k in CONFIG_KEYS and v is not None:
            _write_config(db, CONFIG_KEYS[k], str(v))
            if k in {"api_key", "base_url"}:
                invalidate_test = True
    # Changer la cle ou l'endpoint invalide le dernier test reussi.
    if invalidate_test:
        _write_config(db, LLM_TESTED_KEY, "false")
    db.commit()


def get_llm_enabled(db: Session) -> bool:
    """Etat de l'interrupteur LLM (defaut: active)."""
    try:
        return _read_config(db, LLM_ENABLED_KEY, "true").strip().lower() in {"1", "true", "yes"}
    except SQLAlchemyError:
        db.rollback()
        return True


def set_llm_enabled(db: Session, enabled: bool) -> None:
    _write_config(db, LLM_ENABLED_KEY, "true" if enabled else "false")
    db.commit()


def get_llm_tested(db: Session) -> bool:
    """Dernier test de connexion Mistral reussi ? (defaut: false)."""
    try:
        return _read_config(db, LLM_TESTED_KEY, "false").strip().lower() in {"1", "true", "yes"}
    except SQLAlchemyError:
        db.rollback()
        return False


def set_llm_tested(db: Session, ok: bool) -> None:
    _write_config(db, LLM_TESTED_KEY, "true" if ok else "false")
    db.commit()


class MistralClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        chat_model: str,
        embed_model: str,
        vision_model: str = "mistral-small-latest",
        ocr_model: str = "mistral-ocr-latest",
        transcribe_model: str = DEFAULT_TRANSCRIBE_MODEL,
        transcribe_api_key: str = "",
        transcribe_base_url: str = "",
    ) -> None:
        if not api_key:
            raise MistralError("MISTRAL_API_KEY non configurée. Renseigne-la dans Paramètres.")
        self.api_key = api_key
        self.base_url = _normalize_base_url(base_url)
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.vision_model = vision_model
        self.ocr_model = ocr_model
        self.transcribe_model = transcribe_model
        # Cle/URL DEDIEES a Voxtral. Vides -> repli sur la cle/URL principale
        # (transcription inchangee tant qu'aucune cle dediee n'est renseignee).
        self.transcribe_api_key = transcribe_api_key or api_key
        self.transcribe_base_url = _normalize_base_url(transcribe_base_url or base_url)
        # Vrai uniquement si une cle Voxtral DEDIEE a ete fournie (pilote le
        # test/liste par API : on ne teste Voxtral separement que dans ce cas).
        self.transcribe_dedicated = bool(transcribe_api_key)

    @classmethod
    def from_db(cls, db: Session) -> "MistralClient":
        s = get_effective_settings(db)
        return cls(
            api_key=s["api_key"],
            base_url=s["base_url"],
            chat_model=s["chat_model"],
            embed_model=s["embed_model"],
            vision_model=s.get("vision_model") or "mistral-small-latest",
            ocr_model=s.get("ocr_model") or "mistral-ocr-latest",
            transcribe_model=s.get("transcribe_model") or DEFAULT_TRANSCRIBE_MODEL,
            transcribe_api_key=s.get("voxtral_api_key") or "",
            transcribe_base_url=s.get("voxtral_base_url") or "",
        )

    def transcribe_audio(
        self,
        audio: bytes,
        filename: str = "dictation.webm",
        *,
        language: Optional[str] = None,
        timeout: float = 120.0,
    ) -> str:
        """Transcrit un audio dicte via Voxtral (POST /v1/audio/transcriptions).

        Multipart : le header Content-Type JSON de `_headers()` ne convient pas —
        httpx pose le boundary multipart lui-meme. Renvoie le texte transcrit.
        """
        files = {"file": (filename, audio, "application/octet-stream")}
        data: dict[str, str] = {"model": self.transcribe_model}
        if language:
            data["language"] = language
        # Cle/URL dediees Voxtral (= principale si non renseignees, cf. __init__).
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{self.transcribe_base_url}/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.transcribe_api_key}"},
                files=files,
                data=data,
            )
            r.raise_for_status()
            return (r.json().get("text") or "").strip()

    async def create_realtime_token(self, timeout: float = 30.0) -> str:
        """Cree un jeton navigateur court pour Voxtral Realtime."""
        headers = {
            "Authorization": f"Bearer {self.transcribe_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"purpose": "realtime", "model": REALTIME_TRANSCRIBE_MODEL}
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.transcribe_base_url}/v1/client/sessions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        secret = (response.json().get("client_secret") or {}).get("value")
        if not isinstance(secret, str) or not secret.startswith("rt_"):
            raise MistralError("Jeton Voxtral Realtime invalide.")
        return secret

    def realtime_websocket_url(self) -> str:
        """Construit l'URL WebSocket Realtime depuis l'URL Voxtral configuree."""
        if self.transcribe_base_url.startswith("https://"):
            base_url = "wss://" + self.transcribe_base_url.removeprefix("https://")
        elif self.transcribe_base_url.startswith("http://"):
            base_url = "ws://" + self.transcribe_base_url.removeprefix("http://")
        else:
            base_url = self.transcribe_base_url
        return (
            f"{base_url}/v1/audio/transcriptions/realtime"
            f"?model={REALTIME_TRANSCRIBE_MODEL}"
        )

    async def transcribe_audio_stream(
        self,
        audio: bytes,
        filename: str = "dictation.webm",
        *,
        language: Optional[str] = None,
        timeout: float = 120.0,
    ) -> AsyncIterator[str]:
        """Diffuse les deltas Voxtral recus en SSE pour un fichier audio."""
        files = {"file": (filename, audio, "application/octet-stream")}
        data: dict[str, str] = {"model": self.transcribe_model, "stream": "true"}
        if language:
            data["language"] = language
        headers = {
            "Authorization": f"Bearer {self.transcribe_api_key}",
            "Accept": "text/event-stream",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.transcribe_base_url}/v1/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("Voxtral SSE event ignored: invalid JSON")
                        continue
                    event_type = str(event.get("type") or "")
                    if event_type.endswith("error"):
                        raise MistralError(str(event.get("error") or "Voxtral stream error"))
                    if event_type.endswith("text.delta"):
                        delta = event.get("text")
                        if isinstance(delta, str) and delta:
                            yield delta

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _list_models_at(self, base_url: str, api_key: str) -> list[str]:
        """GET /v1/models sur une API donnee (cle/URL explicites)."""
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                f"{base_url.rstrip('/')}/v1/models",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
            return [m.get("id", "") for m in data.get("data", [])]

    def list_models(self) -> list[str]:
        """Modeles de l'API Mistral principale (chat/embed/vision/ocr)."""
        return self._list_models_at(self.base_url, self.api_key)

    def list_transcribe_models(self) -> list[str]:
        """Modeles de l'API DEDIEE a la transcription (Voxtral). Identique a
        list_models si aucune cle dediee n'est configuree (meme endpoint)."""
        return self._list_models_at(self.transcribe_base_url, self.transcribe_api_key)

    def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.0,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Appel chat non streame, sortie forcee en JSON object.

        Utilise par le remplissage de template .pptx : on demande au modele
        de produire un mapping `{placeholder: contenu}`. Levee `MistralError`
        si la reponse n'est pas du JSON valide.
        """
        payload = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise MistralError("Reponse Mistral vide.")
        content = (choices[0].get("message") or {}).get("content") or ""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise MistralError(f"Reponse non-JSON : {e}") from e
        if not isinstance(parsed, dict):
            raise MistralError("Reponse JSON n'est pas un objet.")
        return parsed

    def translate_batch(
        self,
        texts: list[str],
        target_lang: str,
        *,
        model: Optional[str] = None,
        timeout: float = 120.0,
    ) -> list[str]:
        """Traduit une liste de chaines vers `target_lang` (fr|en|es) en UN appel
        JSON. Conserve noms propres / acronymes / nombres, preserve la casse, et
        laisse une chaine inchangee si elle est deja dans la langue cible. En cas
        d'echec ou de longueur incoherente, renvoie les chaines d'origine."""
        if not texts:
            return []
        lang_name = _LANG_NAMES.get(target_lang, "French")
        system = (
            f"You are a professional translator. Translate each string of the "
            f"input JSON array into {lang_name}. RULES: keep proper nouns, "
            f"person and company names, emails, URLs, numbers and acronyms "
            f"unchanged; preserve capitalization style (an UPPERCASE label stays "
            f"UPPERCASE); if a string is ALREADY in {lang_name}, return it "
            f"verbatim. Return STRICTLY a JSON object "
            f'{{"translations": [...]}} with the SAME number of items in the '
            f"SAME order."
        )
        user = json.dumps(texts, ensure_ascii=False)
        try:
            raw = self.chat_json(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                model=model,
                temperature=0.0,
                timeout=timeout,
            )
        except MistralError:
            return texts
        out = raw.get("translations")
        if not isinstance(out, list) or len(out) != len(texts):
            return texts
        return [str(out[i]) if out[i] is not None else texts[i] for i in range(len(texts))]

    def embed(self, inputs: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{self.base_url}/v1/embeddings",
                headers=self._headers(),
                json={"model": self.embed_model, "input": inputs},
            )
            r.raise_for_status()
            data = r.json()
            return [item["embedding"] for item in data["data"]]

    def ocr_pdf(
        self,
        pdf_bytes: bytes,
        *,
        model: Optional[str] = None,
        timeout: float = 180.0,
    ) -> str:
        """OCR document via l'API Mistral (POST /v1/ocr).

        Le PDF est transmis en data-URI base64 (pas de Files API : un seul
        round-trip, suffisant pour un CV). Renvoie le markdown concatene des
        pages (l'API comprend colonnes/tableaux, bien mieux que Tesseract).
        Leve `MistralError` si la reponse ne contient aucun texte ; les erreurs
        HTTP httpx remontent telles quelles (l'appelant fait le repli).
        """
        import base64

        b64 = base64.b64encode(pdf_bytes).decode("ascii")
        payload = {
            "model": model or self.ocr_model,
            "document": {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{b64}",
            },
        }
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{self.base_url}/v1/ocr",
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        pages = data.get("pages") or []
        parts = [(p.get("markdown") or "") for p in pages]
        text = "\n\n".join(s for s in parts if s.strip())
        if not text.strip():
            raise MistralError("OCR Mistral : reponse sans texte exploitable.")
        return text

    def vision_extract(
        self,
        images_png: list[bytes],
        *,
        model: Optional[str] = None,
        timeout: float = 240.0,
    ) -> str:
        """Transcription VISION : envoie les pages (images PNG) a un modele
        multimodal et demande une transcription FIDELE qui INTERPRETE aussi le
        graphique (drapeaux -> langue, barres/points -> niveau). Renvoie le
        texte. Leve `MistralError` si la reponse est vide.
        """
        import base64

        content: list[dict[str, Any]] = [{"type": "text", "text": _VISION_PROMPT}]
        for img in images_png:
            b64 = base64.b64encode(img).decode("ascii")
            content.append(
                {"type": "image_url", "image_url": f"data:image/png;base64,{b64}"}
            )
        payload = {
            "model": model or self.vision_model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.0,
        }
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise MistralError("Vision Mistral : reponse vide.")
        text = (choices[0].get("message") or {}).get("content") or ""
        if not text.strip():
            raise MistralError("Vision Mistral : transcription vide.")
        return text

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        obj = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
