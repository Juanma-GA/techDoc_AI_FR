"""Assistant conversationnel : genere puis modifie iterativement un logigramme.

Chaque tour envoie a Mistral l'historique de conversation et le graphe courant ;
le modele renvoie {"reply", "graph"} ou graph est le logigramme COMPLET modifie
(ou null si aucune modification). Sans LLM : repli gracieux, jamais de 5xx.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled
from app.flow.attachments import looks_structured
from app.flow.model import FlowGraph
from app.flow.parsers.json_dsl import graph_from_dict, parse_json_or_dsl
from app.flow.parsers.text_llm import SYSTEM_PROMPT, clip_graph_dict, fallback_parse, load_json_object

log = structlog.get_logger("flowchart_generator.assistant")

MAX_HISTORY = 20
MAX_DOC_CONTEXT = 120_000

ASSISTANT_PROMPT = (
    SYSTEM_PROMPT
    + """

MODE ASSISTANT (cette consigne remplace le format de reponse ci-dessus).
Tu dialogues avec un technicien redacteur pour construire puis affiner un logigramme / plan de maintenance.
- Sans logigramme courant : genere-le a partir de la demande.
- Avec un logigramme courant : applique UNIQUEMENT les modifications demandees, conserve les ids,
  libelles et liens non concernes, et renvoie le logigramme COMPLET mis a jour.
- Si la demande est une question ou n'implique aucune modification : graph = null.
Reponds UNIQUEMENT par un objet JSON {"reply": str, "graph": <logigramme au format ci-dessus> | null}.
`reply` = 1 a 3 phrases dans la langue de l'utilisateur, resumant ce qui a ete fait ou repondant
a la question, eventuellement une suggestion d'amelioration (securite, controle manquant)."""
)


@dataclass
class AssistantTurn:
    reply: str
    graph: FlowGraph | None = None
    llm_used: bool = False
    warnings: list[str] = field(default_factory=list)


def parse_envelope(raw: str) -> tuple[str, FlowGraph | None]:
    data = load_json_object(raw)
    if not isinstance(data, dict):
        raise ValueError("enveloppe JSON attendue")
    reply = str(data.get("reply") or "").strip()[:4000]
    raw_graph = data.get("graph")
    graph = graph_from_dict(clip_graph_dict(raw_graph)) if isinstance(raw_graph, dict) else None
    return reply or "Logigramme mis a jour.", graph


def _context(graph: FlowGraph | None, documents: list[dict[str, str]]) -> str:
    parts = []
    budget = MAX_DOC_CONTEXT
    for doc in documents:
        if budget <= 0:
            break
        text = doc["text"][:budget]
        budget -= len(text)
        parts.append(f"--- Document joint : {doc['name']} ---\n{text}")
    if parts:
        parts.insert(0, "Documents de reference fournis par l'utilisateur (sources a exploiter) :")
    if graph is None:
        parts.append("Aucun logigramme courant : genere-en un nouveau.")
    else:
        parts.append("Logigramme courant (JSON) :\n" + graph.model_dump_json(exclude_none=True))
    return "\n\n".join(parts)


def _import_pasted(last: str) -> AssistantTurn | None:
    if not looks_structured(last):
        return None
    try:
        graph, warnings = parse_json_or_dsl(last)
    except AppError:
        return None
    return AssistantTurn(
        reply=f"Logigramme importe : {len(graph.nodes)} etapes, {len(graph.edges)} liens.",
        graph=graph,
        warnings=warnings,
    )


def _fallback(
    graph: FlowGraph | None, last: str, reason: str, documents: list[dict[str, str]]
) -> AssistantTurn:
    if graph is not None:
        return AssistantTurn(
            reply=f"{reason} Modification en langage naturel impossible : joignez un fichier "
            "JSON / DSL / Excel corrige, ou activez Mistral dans Parametres.",
            warnings=[reason],
        )
    try:
        new_graph, warnings = fallback_parse(last)
    except AppError:
        if not documents:
            return AssistantTurn(
                reply=f"{reason} Decrivez la procedure, une etape par ligne.", warnings=[reason]
            )
        try:
            new_graph, warnings = fallback_parse(documents[0]["text"][:20000])
        except AppError:
            return AssistantTurn(
                reply=f"{reason} Decrivez la procedure, une etape par ligne.", warnings=[reason]
            )
    return AssistantTurn(
        reply=f"{reason} Logigramme genere sans IA (une ligne = une etape). "
        "Activez Mistral dans Parametres pour iterer en langage naturel.",
        graph=new_graph,
        warnings=[reason, *warnings],
    )


async def assistant_turn(
    db: Session,
    messages: list[dict[str, str]],
    graph: FlowGraph | None,
    documents: list[dict[str, str]] | None = None,
) -> AssistantTurn:
    documents = documents or []
    last = messages[-1]["content"]
    pasted = _import_pasted(last)
    if pasted is not None:
        return pasted
    if not get_llm_enabled(db):
        return _fallback(graph, last, "LLM desactive.", documents)
    try:
        client = MistralClient.from_db(db)
        payload = [{"role": "system", "content": ASSISTANT_PROMPT + "\n\n" + _context(graph, documents)}]
        payload += [{"role": m["role"], "content": m["content"][:20000]} for m in messages[-MAX_HISTORY:]]
        chunks = [delta async for delta in client.chat_stream(payload, temperature=0.1)]
        reply, new_graph = parse_envelope("".join(chunks))
        return AssistantTurn(reply=reply, graph=new_graph, llm_used=True)
    except MistralError as exc:
        log.warning("assistant_fallback", reason=type(exc).__name__)
        reason = "LLM non configure."
    except (AppError, ValueError, ValidationError) as exc:
        log.warning("assistant_fallback", reason=type(exc).__name__)
        reason = "Reponse LLM inexploitable."
    except Exception as exc:  # erreurs reseau httpx et assimilees -> repli gracieux
        log.warning("assistant_fallback", reason=type(exc).__name__)
        reason = "LLM injoignable."
    return _fallback(graph, last, reason, documents)
