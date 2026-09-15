"""Routes /api/v1/sessions — sessions de génération + SSE ask."""

from __future__ import annotations

import json
import logging
import traceback
import uuid

import httpx
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.auth import AuthenticatedUser, require_authenticated
from app.core.errors import AppError
from app.core.mistral_client import (
    REALTIME_TRANSCRIBE_MODEL,
    MistralClient,
    MistralError,
    get_llm_enabled,
)
from app.core.ownership import get_owned_session
from app.core.writer_engine import ensure_session_title, stream_answer
from app.db.models import Document, Message
from app.db.models import Session as SessionRow
from app.db.session import SessionLocal, get_db
from app.schemas import (
    AskIn,
    MessageOut,
    RealtimeTranscriptionTokenOut,
    SessionCreateIn,
    SessionOut,
    TranscriptionOut,
)

# Formats audio acceptes pour la dictee (MediaRecorder produit surtout du webm/ogg).
_AUDIO_EXTS = (".webm", ".ogg", ".oga", ".mp3", ".m4a", ".wav", ".mp4", ".flac")
_MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 Mo (~20 min de dictee)


log = logging.getLogger("doc_writer.sessions")

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/transcribe/realtime-token", response_model=RealtimeTranscriptionTokenOut)
async def create_realtime_transcription_token(
    db: Session = Depends(get_db),
) -> RealtimeTranscriptionTokenOut:
    """Emet un jeton court pour connecter le navigateur a Voxtral Realtime."""
    if not get_llm_enabled(db):
        return RealtimeTranscriptionTokenOut(
            enabled=False,
            token="",
            model=REALTIME_TRANSCRIBE_MODEL,
            websocket_url="",
        )
    try:
        client = MistralClient.from_db(db)
        token = await client.create_realtime_token()
    except MistralError as exc:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(exc), 400) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = (exc.response.text or "")[:300]
        raise AppError(
            "REALTIME_TOKEN_FAILED",
            f"Connexion Voxtral Realtime refusee (HTTP {status}).",
            502,
            detail={"status": status, "response": detail},
        ) from exc
    return RealtimeTranscriptionTokenOut(
        enabled=True,
        token=token,
        model=REALTIME_TRANSCRIBE_MODEL,
        websocket_url=client.realtime_websocket_url(),
    )


@router.post("/transcribe", response_model=TranscriptionOut)
async def transcribe(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> TranscriptionOut:
    """Transcrit une dictee vocale (Voxtral) → texte a injecter dans le brief.

    L'insertion intelligente dans le template est ensuite assuree par le flux de
    generation/remplissage existant (le texte devient/augmente le brief)."""
    # LLM OFF → fallback gracieux : 200 + texte vide (jamais 5xx, regle #6).
    if not get_llm_enabled(db):
        return TranscriptionOut(text="", llm_used=False)

    name = (file.filename or "audio.webm").lower()
    if not name.endswith(_AUDIO_EXTS):
        raise AppError("BAD_AUDIO", f"Format audio non supporte ({name}).", 400)
    audio = await file.read()
    if not audio:
        raise AppError("EMPTY_AUDIO", "Audio vide.", 400)
    if len(audio) > _MAX_AUDIO_BYTES:
        raise AppError("AUDIO_TOO_LARGE", "Audio trop volumineux (max 25 Mo).", 413)

    try:
        client = MistralClient.from_db(db)
    except MistralError as exc:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(exc), 400) from exc
    try:
        text = client.transcribe_audio(audio, filename=name)
    except httpx.HTTPStatusError as exc:
        # L'API a repondu 4xx/5xx. Cas courant : le modele Voxtral n'est pas
        # active sur la cle -> message explicite (l'utilisateur en choisit un
        # autre en Parametres). Sinon on remonte code + corps pour diagnostiquer.
        status = exc.response.status_code
        body = (exc.response.text or "")[:300]
        log.warning("Voxtral transcription HTTP %s: %s", status, body)
        low = body.lower()
        if "invalid_model" in low or "invalid model" in low or status in (403, 404):
            msg = (
                f"Le modele de transcription « {client.transcribe_model} » n'est pas "
                "active sur cette cle Mistral (Voxtral indisponible). Choisis-en un "
                "autre dans Parametres > Mistral (« Tester la connexion » liste les "
                "modeles disponibles)."
            )
        else:
            msg = f"Transcription refusee par Mistral (HTTP {status}). {body}"
        raise AppError(
            "TRANSCRIBE_FAILED", msg, 502,
            detail={"status": status, "model": client.transcribe_model},
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "TRANSCRIBE_FAILED", f"Transcription echouee : {type(exc).__name__}", 502
        ) from exc
    return TranscriptionOut(text=text, llm_used=True)


@router.post("/transcribe/stream")
async def transcribe_stream(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Transcrit une dictee avec Voxtral Realtime et relaie ses deltas en SSE."""
    if not get_llm_enabled(db):
        async def disabled_gen():
            yield {"event": "done", "data": json.dumps({"llm_used": False})}

        return EventSourceResponse(disabled_gen())

    name = (file.filename or "audio.webm").lower()
    if not name.endswith(_AUDIO_EXTS):
        raise AppError("BAD_AUDIO", f"Format audio non supporte ({name}).", 400)
    audio = await file.read()
    if not audio:
        raise AppError("EMPTY_AUDIO", "Audio vide.", 400)
    if len(audio) > _MAX_AUDIO_BYTES:
        raise AppError("AUDIO_TOO_LARGE", "Audio trop volumineux (max 25 Mo).", 413)

    try:
        client = MistralClient.from_db(db)
    except MistralError as exc:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(exc), 400) from exc

    async def event_gen():
        try:
            async for delta in client.transcribe_audio_stream(audio, filename=name):
                yield {"event": "token", "data": delta}
            yield {"event": "done", "data": json.dumps({"llm_used": True})}
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = (exc.response.text or "")[:300]
            log.warning("Voxtral streaming transcription HTTP %s: %s", status, body)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": f"Transcription refusee par Mistral (HTTP {status}). {body}"}
                ),
            }
        except Exception as exc:
            log.exception("Voxtral streaming transcription failed")
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": f"Transcription echouee : {type(exc).__name__}"}
                ),
            }

    return EventSourceResponse(event_gen())


def _require_owned_doc_ids(
    db: Session, doc_ids: list[uuid.UUID], user: AuthenticatedUser | None
) -> None:
    """§3 (MFA pilot) : `scope_doc_ids`/`template_doc_id`/`style_doc_id`
    pointent directement vers du contenu de document que writer_engine.py lit
    par id sans autre verification -- sans ce garde-fou, une session pourrait
    referencer le document d'un AUTRE utilisateur et faire fuiter son contenu
    dans la generation. 400, pas 404 : la ref vient du corps de la requete
    de l'appelant lui-meme, ce n'est pas une navigation d'URL."""
    if user is None or not doc_ids:
        return
    owned = set(
        db.scalars(
            select(Document.id).where(Document.id.in_(doc_ids), Document.user_email == user.email)
        )
    )
    unauthorized = [str(d) for d in doc_ids if d not in owned]
    if unauthorized:
        raise AppError(
            "DOCUMENT_NOT_OWNED",
            "Un ou plusieurs documents referencs n'appartiennent pas a l'utilisateur courant.",
            status_code=400,
            detail={"document_ids": unauthorized},
        )


@router.get("", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    user: AuthenticatedUser | None = Depends(require_authenticated),
) -> list[SessionRow]:
    stmt = select(SessionRow).order_by(SessionRow.created_at.desc())
    if user is not None:
        stmt = stmt.where(SessionRow.user_email == user.email)
    return list(db.scalars(stmt))


@router.post("", response_model=SessionOut)
def create_session(
    payload: SessionCreateIn,
    db: Session = Depends(get_db),
    user: AuthenticatedUser | None = Depends(require_authenticated),
) -> SessionRow:
    all_referenced = list(payload.scope_doc_ids)
    if payload.template_doc_id is not None:
        all_referenced.append(payload.template_doc_id)
    if payload.style_doc_id is not None:
        all_referenced.append(payload.style_doc_id)
    _require_owned_doc_ids(db, all_referenced, user)

    scope_json = json.dumps([str(d) for d in payload.scope_doc_ids])
    session = SessionRow(
        title=payload.title or "",
        scope_doc_ids=scope_json,
        lang=payload.lang or "fr",
        output_format=payload.output_format or "markdown",
        length=payload.length or "medium",
        tone=payload.tone or "professional",
        template_doc_id=payload.template_doc_id,
        style_doc_id=payload.style_doc_id,
        user_email=user.email if user else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthenticatedUser | None = Depends(require_authenticated),
) -> None:
    s = get_owned_session(db, session_id, user)
    if s is None:
        raise AppError(
            "SESSION_NOT_FOUND", "Session introuvable.", status_code=404,
            detail={"id": str(session_id)},
        )
    db.delete(s)
    db.commit()


@router.get("/{session_id}/messages", response_model=list[MessageOut])
def list_messages(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthenticatedUser | None = Depends(require_authenticated),
) -> list[Message]:
    s = get_owned_session(db, session_id, user)
    if s is None:
        raise AppError(
            "SESSION_NOT_FOUND", "Session introuvable.", status_code=404,
            detail={"id": str(session_id)},
        )
    return list(s.messages)


@router.post("/{session_id}/ask")
async def ask(
    session_id: uuid.UUID,
    body: AskIn,
    db: Session = Depends(get_db),
    user: AuthenticatedUser | None = Depends(require_authenticated),
):
    session = get_owned_session(db, session_id, user)
    if session is None:
        raise AppError(
            "SESSION_NOT_FOUND", "Session introuvable.", status_code=404,
            detail={"id": str(session_id)},
        )

    # Interrupteur LLM OFF : on ne lance pas la generation. SSE 200 avec un
    # event `error` gracieux (jamais de 5xx), la cle Mistral est conservee.
    if not get_llm_enabled(db):
        async def disabled_gen():
            yield {
                "event": "error",
                "data": json.dumps({"message": "LLM desactive."}),
            }

        return EventSourceResponse(disabled_gen())

    try:
        mistral = MistralClient.from_db(db)
    except MistralError as e:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(e), status_code=400) from e

    ensure_session_title(db, session, body.question)
    session_id_val = session.id
    session_title = session.title
    question = body.question

    async def event_gen():
        stream_db = SessionLocal()
        try:
            s_session = stream_db.get(SessionRow, session_id_val)
            if s_session is None:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": "Session perdue."}),
                }
                return
            yield {
                "event": "session",
                "data": json.dumps(
                    {"session_id": str(session_id_val), "title": session_title}
                ),
            }
            token_count = 0
            try:
                async for delta in stream_answer(stream_db, s_session, question, mistral):
                    token_count += 1
                    yield {"event": "token", "data": delta}
                if token_count == 0:
                    yield {"event": "token", "data": "(Le modèle n'a rien renvoyé.)"}
                yield {"event": "done", "data": "{}"}
            except Exception as e:  # noqa: BLE001
                tb = traceback.format_exc()
                log.error("ask error: %s\n%s", e, tb)
                yield {
                    "event": "error",
                    "data": json.dumps({"message": f"{type(e).__name__}: {e}"}),
                }
        finally:
            stream_db.close()

    return EventSourceResponse(event_gen())
