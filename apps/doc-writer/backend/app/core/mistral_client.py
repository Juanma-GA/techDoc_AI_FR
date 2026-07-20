"""Client Mistral minimal — httpx async (streaming) + httpx sync (embeddings).

Pas de SDK Mistral. La configuration runtime est lue dans la table `app_config`
avec fallback sur `app.config.settings` (qui lit le `.env`).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import AppConfig

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
}

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


def _read_config(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppConfig, key)
    return row.value if row and row.value else default


def _write_config(db: Session, key: str, value: str) -> None:
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=value))
    else:
        row.value = value


def get_effective_settings(db: Session) -> dict[str, str]:
    from app.config import settings as defaults

    return {
        "api_key": _read_config(db, CONFIG_KEYS["api_key"], defaults.mistral_api_key),
        "base_url": _read_config(db, CONFIG_KEYS["base_url"], defaults.mistral_base_url),
        "chat_model": _read_config(db, CONFIG_KEYS["chat_model"], defaults.mistral_chat_model),
        "embed_model": _read_config(db, CONFIG_KEYS["embed_model"], defaults.mistral_embed_model),
        "vision_model": _read_config(
            db, CONFIG_KEYS["vision_model"], defaults.mistral_vision_model
        ),
        "ocr_model": _read_config(db, CONFIG_KEYS["ocr_model"], defaults.mistral_ocr_model),
        "transcribe_model": _read_config(
            db, CONFIG_KEYS["transcribe_model"], defaults.mistral_transcribe_model
        ),
    }


def save_settings(db: Session, data: dict[str, Any]) -> None:
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
        transcribe_model: str = "voxtral-mini-transcribe-26-02",
    ) -> None:
        if not api_key:
            raise MistralError("MISTRAL_API_KEY non configurée. Renseigne-la dans Paramètres.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.vision_model = vision_model
        self.ocr_model = ocr_model
        self.transcribe_model = transcribe_model

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
            transcribe_model=s.get("transcribe_model") or "voxtral-mini-transcribe-26-02",
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
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{self.base_url}/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                data=data,
            )
            r.raise_for_status()
            return (r.json().get("text") or "").strip()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def list_models(self) -> list[str]:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{self.base_url}/v1/models", headers=self._headers())
            r.raise_for_status()
            data = r.json()
            return [m.get("id", "") for m in data.get("data", [])]

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
