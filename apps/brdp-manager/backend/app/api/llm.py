"""Routes /api/v1/llm - proxy Mistral generique (chat + stream).

Remplace le multi-provider (Anthropic/OpenAI/Custom) + le proxy Express de
l'app d'origine : un seul provider (Mistral), cle stockee cote serveur
(cf. regle #6 STANDARD_POC.md). Quand `llm_enabled` est OFF, on renvoie un
resultat vide (HTTP 200, jamais 5xx) au lieu d'echouer.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled
from app.db.session import get_db
from app.schemas import LlmChatIn, LlmChatOut

log = logging.getLogger("brdp_manager.llm")

router = APIRouter(prefix="/llm", tags=["llm"])


def _messages(payload: LlmChatIn) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = []
    if payload.system:
        msgs.append({"role": "system", "content": payload.system})
    msgs.extend({"role": m.role, "content": m.content} for m in payload.messages)
    return msgs


@router.post("/chat", response_model=LlmChatOut)
async def chat(payload: LlmChatIn, db: Session = Depends(get_db)) -> LlmChatOut:
    if not get_llm_enabled(db):
        return LlmChatOut(content="", skipped=True)
    try:
        mistral = MistralClient.from_db(db)
        content = await mistral.chat(_messages(payload), temperature=payload.temperature)
    except MistralError as e:
        return LlmChatOut(content=f"[LLM error] {e}", skipped=True)
    except Exception as e:  # noqa: BLE001
        log.exception("llm chat failed")
        return LlmChatOut(content=f"[LLM error] {type(e).__name__}: {e}", skipped=True)
    return LlmChatOut(content=content)


@router.post("/chat/stream")
async def chat_stream(payload: LlmChatIn, db: Session = Depends(get_db)) -> StreamingResponse:
    if not get_llm_enabled(db):

        async def _empty():
            yield f"data: {json.dumps({'error': 'LLM desactive'})}\n\n"

        return StreamingResponse(_empty(), media_type="text/event-stream")

    try:
        mistral = MistralClient.from_db(db)
    except MistralError as e:
        async def _err():
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(_err(), media_type="text/event-stream")

    async def _gen():
        try:
            async for chunk in mistral.chat_stream(
                _messages(payload), temperature=payload.temperature
            ):
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
        except Exception as e:  # noqa: BLE001
            log.exception("llm chat stream failed")
            yield f"data: {json.dumps({'error': f'{type(e).__name__}: {e}'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")
