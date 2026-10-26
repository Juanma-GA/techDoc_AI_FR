"""GET/POST /api/v1/chat — sessions multi-scope + ask SSE."""

from __future__ import annotations

import json
import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.chat_engine import (
    get_or_create_session,
    session_scope_ids,
    stream_answer,
)
from app.core.errors import AppError
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled, requires_llm
from app.core.prompt_sanitizer import sanitize_prompt
from app.db.models import ChatMessage, ChatSession, Project
from app.db.session import SessionLocal, get_db
from app.schemas import ChatAskIn, ChatMessageOut, ChatSessionOut
from app.core.plain_text import strip_markdown


log = logging.getLogger("corpus-agent.chat")

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(db: Session = Depends(get_db)) -> list[ChatSession]:
    """Liste TOUTES les sessions, multi-scope inclus (plus de filtre projet_id)."""
    return list(db.scalars(select(ChatSession).order_by(ChatSession.created_at.desc())))


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(session_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ChatMessageOut]:
    s = db.get(ChatSession, session_id)
    if s is None:
        raise AppError("CHAT_SESSION_NOT_FOUND", "Session introuvable",
                       status_code=404, detail={"id": str(session_id)})
    out: list[ChatMessageOut] = []
    for m in s.messages:
        item = ChatMessageOut.model_validate(m)
        # Anciennes reponses enregistrees avec du Markdown : affichees en texte brut
        if item.role == "assistant":
            item = item.model_copy(update={"content": strip_markdown(item.content)})
        out.append(item)
    return out


@router.delete("/sessions/{session_id}", status_code=204, response_class=Response)
def delete_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    s = db.get(ChatSession, session_id)
    if s is None:
        raise AppError("CHAT_SESSION_NOT_FOUND", "Session introuvable",
                       status_code=404, detail={"id": str(session_id)})
    db.delete(s)
    db.commit()
    return Response(status_code=204)


def _resolve_projects(db: Session, project_ids: list[uuid.UUID]) -> list[Project]:
    """Liste vide → tous les projets. Sinon, valide chaque ID."""
    if not project_ids:
        return []
    out: list[Project] = []
    for pid in project_ids:
        p = db.get(Project, pid)
        if p is None:
            raise AppError(
                "PROJECT_NOT_FOUND",
                f"Projet introuvable : {pid}",
                status_code=404,
                detail={"id": str(pid)},
            )
        out.append(p)
    return out


@router.post("/ask")
@requires_llm("corpus-agent.chat.ask")
async def ask(body: ChatAskIn, db: Session = Depends(get_db)):
    projects = _resolve_projects(db, list(body.project_ids))

    # Interrupteur global IA : le chatbot dépend entièrement du LLM. Si OFF, on
    # réutilise le même garde-fou que « Mistral non configuré » → 400 explicite
    # (jamais de 5xx), sans toucher à la clé.
    if not get_llm_enabled(db):
        raise AppError(
            "LLM_DISABLED",
            "L'assistant IA est desactive. Reactivez le LLM dans Parametres.",
            status_code=400,
        )

    try:
        mistral = MistralClient.from_db(db)
    except MistralError as e:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(e), status_code=400) from e

    # Defense anti-injection : on assainit la question utilisateur avant qu'elle
    # n'atteigne le LLM (et avant de l'utiliser comme titre de session).
    sanitized_question = sanitize_prompt(body.question, context="chat_message")

    session = get_or_create_session(db, [p.id for p in projects], body.session_id, sanitized_question)

    # Si la session existe déjà → reprendre son scope (pas celui du body).
    scope_ids = session_scope_ids(session)
    if scope_ids and not body.project_ids:
        # session existante avec scope explicite → on reprend ce scope
        projects = _resolve_projects(db, scope_ids)

    session_id = session.id
    session_title = session.title
    project_ids_for_stream = [p.id for p in projects]
    question = sanitized_question
    lang = body.lang or "fr"

    async def event_gen():
        stream_db = SessionLocal()
        try:
            stream_projects = [stream_db.get(Project, pid) for pid in project_ids_for_stream]
            stream_projects = [p for p in stream_projects if p is not None]
            s_session = stream_db.get(ChatSession, session_id)
            yield {"event": "session", "data": json.dumps(
                {"session_id": str(session_id), "title": session_title}
            )}
            token_count = 0
            try:
                async for delta in stream_answer(stream_db, stream_projects, s_session, question, mistral, lang=lang):
                    token_count += 1
                    yield {"event": "token", "data": delta}
                if token_count == 0:
                    yield {"event": "token", "data": "(Le modèle n'a rien renvoyé.)"}
                yield {"event": "done", "data": "{}"}
            except Exception as e:  # noqa: BLE001
                tb = traceback.format_exc()
                log.error("chat error: %s\n%s", e, tb)
                yield {"event": "error", "data": json.dumps({"message": f"{type(e).__name__}: {e}"})}
        finally:
            stream_db.close()

    return EventSourceResponse(event_gen())
