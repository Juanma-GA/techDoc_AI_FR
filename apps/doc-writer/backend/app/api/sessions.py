"""Routes /api/v1/sessions — sessions de génération + SSE ask."""

from __future__ import annotations

import json
import logging
import traceback
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.errors import AppError
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled
from app.core.writer_engine import ensure_session_title, stream_answer
from app.db.models import Message, Session as SessionRow
from app.db.session import SessionLocal, get_db
from app.schemas import AskIn, MessageOut, SessionCreateIn, SessionOut


log = logging.getLogger("doc_writer.sessions")

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)) -> list[SessionRow]:
    return list(db.scalars(select(SessionRow).order_by(SessionRow.created_at.desc())))


@router.post("", response_model=SessionOut)
def create_session(payload: SessionCreateIn, db: Session = Depends(get_db)) -> SessionRow:
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
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    s = db.get(SessionRow, session_id)
    if s is None:
        raise AppError(
            "SESSION_NOT_FOUND", "Session introuvable.", status_code=404,
            detail={"id": str(session_id)},
        )
    db.delete(s)
    db.commit()


@router.get("/{session_id}/messages", response_model=list[MessageOut])
def list_messages(session_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Message]:
    s = db.get(SessionRow, session_id)
    if s is None:
        raise AppError(
            "SESSION_NOT_FOUND", "Session introuvable.", status_code=404,
            detail={"id": str(session_id)},
        )
    return list(s.messages)


@router.post("/{session_id}/ask")
async def ask(session_id: uuid.UUID, body: AskIn, db: Session = Depends(get_db)):
    session = db.get(SessionRow, session_id)
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
