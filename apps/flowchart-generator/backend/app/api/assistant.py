"""Routes /api/v1/assistant/* : assistant de generation / modification de logigramme.

chat   : un tour de conversation (historique + logigramme courant + documents joints).
attach : piece jointe -> logigramme importe (Excel/CSV/JSON/DSL) ou document de reference.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.convert import MAX_UPLOAD_BYTES
from app.core.errors import AppError
from app.db.session import get_db
from app.flow.assistant import assistant_turn
from app.flow.attachments import read_attachment
from app.schemas import AssistantAttachOut, AssistantChatIn, AssistantChatOut

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=AssistantChatOut)
async def assistant_chat(body: AssistantChatIn, db: Session = Depends(get_db)) -> AssistantChatOut:
    if body.messages[-1].role != "user":
        raise AppError("ASSISTANT_TURN", "Le dernier message doit venir de l'utilisateur", status_code=422)
    messages = [m.model_dump() for m in body.messages]
    documents = [d.model_dump() for d in body.documents]
    turn = await assistant_turn(db, messages, body.graph, documents)
    return AssistantChatOut(
        message=turn.reply,
        graph=turn.graph,
        changed=turn.graph is not None,
        llm_used=turn.llm_used,
        warnings=turn.warnings,
    )


@router.post("/attach", response_model=AssistantAttachOut)
async def assistant_attach(file: UploadFile = File(...)) -> AssistantAttachOut:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise AppError("FILE_TOO_LARGE", "Fichier trop volumineux (5 Mo max)", status_code=413)
    att = read_attachment(file.filename or "", content)
    return AssistantAttachOut(
        kind=att.kind,
        name=att.name,
        graph=att.graph,
        text=att.text,
        truncated=att.truncated,
        warnings=att.warnings,
    )
