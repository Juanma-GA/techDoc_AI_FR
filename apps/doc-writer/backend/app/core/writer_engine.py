"""Moteur de génération RAG : assemblage du contexte + streaming.

Différent d'un chat Q&R : le system prompt vise une production rédactionnelle
longue et structurée (markdown), avec citations [filename] obligatoires.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.indexer import search_similar
from app.core.mistral_client import MistralClient
from app.db.models import Document, Message, Session as SessionRow


SYSTEM_PROMPT_FR = (
    "Tu es un assistant de rédaction technique. À partir d'un brief utilisateur et d'extraits "
    "de documents fournis, tu produis un contenu structuré, factuel et complet en MARKDOWN "
    "(titres, listes, paragraphes — pas de blocs de code sauf si pertinent).\n"
    "Tu cites systématiquement tes sources sous la forme [nom_fichier] après chaque affirmation "
    "factuelle qui s'appuie sur un extrait.\n"
    "Si une information demandée par le brief n'est pas dans les extraits, indique-le "
    "explicitement plutôt que d'inventer.\n"
    "Ne reproduis pas le brief dans ta réponse, livre directement le contenu rédigé."
)

SYSTEM_PROMPT_EN = (
    "You are a technical writing assistant. From a user brief and provided document excerpts, "
    "you produce structured, factual, complete content in MARKDOWN (headings, lists, "
    "paragraphs — no code blocks unless relevant).\n"
    "You systematically cite your sources as [file_name] after each factual claim that relies "
    "on an excerpt.\n"
    "If a piece of information requested in the brief is not in the excerpts, say so explicitly "
    "instead of inventing it.\n"
    "Do not repeat the brief in your answer, deliver the written content directly."
)


def system_prompt(lang: str) -> str:
    return SYSTEM_PROMPT_EN if lang == "en" else SYSTEM_PROMPT_FR


# Préambules à concaténer au system prompt selon les options de la Session.
# Volontairement en français — les directives au LLM marchent dans toutes les
# langues et c'est plus facile à maintenir (un seul jeu de prompts).

FORMAT_PROMPTS: dict[str, str] = {
    "markdown": "",  # comportement par défaut
    "faq": (
        "FORMAT IMPOSÉ : produit une FAQ de 5 à 10 paires Question/Réponse. "
        "Chaque question commence par « **Q : » et chaque réponse par « **R : »."
    ),
    "structured": (
        "FORMAT IMPOSÉ : structure ta réponse avec ces 4 sections obligatoires "
        "(titres `##`) : Contexte, Constat, Recommandations, Risques."
    ),
    "table": (
        "FORMAT IMPOSÉ : réponds principalement avec un ou plusieurs tableaux "
        "markdown comparatifs (pipes, en-têtes en gras). Un court paragraphe "
        "d'introduction avant le tableau est autorisé."
    ),
    "template": (
        "FORMAT IMPOSÉ : tu reçois un TEMPLATE avec des placeholders du type "
        "`{{nom_du_placeholder}}`. Remplis CHAQUE placeholder à partir des "
        "extraits fournis. Si une valeur n'est pas dans les extraits, écris "
        "`{{nom}} = NON TROUVÉ`. Renvoie le template entier rempli, sans "
        "préambule ni explication."
    ),
}

LENGTH_HINTS: dict[str, str] = {
    "short":  "LONGUEUR : réponse courte, 1 paragraphe maximum (~150 mots).",
    "medium": "LONGUEUR : réponse moyenne, 2-4 paragraphes (~400 mots).",
    "long":   "LONGUEUR : réponse longue et détaillée, 1-2 pages (~1000 mots).",
}

TONE_HINTS: dict[str, str] = {
    "professional": "TON : professionnel, factuel, neutre.",
    "pedagogical":  "TON : pédagogique, comme une explication progressive à un débutant.",
    "technical":    "TON : technique et précis, lexique spécialisé autorisé.",
    "synthetic":    "TON : très synthétique, va à l'essentiel, pas de redite.",
}


def _build_options_preamble(session: SessionRow) -> str:
    """Concatène les directives format / longueur / ton issues de la session."""
    parts: list[str] = []
    fmt = (session.output_format or "markdown").strip()
    if fmt in FORMAT_PROMPTS and FORMAT_PROMPTS[fmt]:
        parts.append(FORMAT_PROMPTS[fmt])
    length = (session.length or "medium").strip()
    if length in LENGTH_HINTS:
        parts.append(LENGTH_HINTS[length])
    tone = (session.tone or "professional").strip()
    if tone in TONE_HINTS:
        parts.append(TONE_HINTS[tone])
    return "\n\n".join(parts)


def _load_doc_text(db: Session, doc_id: Optional[uuid.UUID]) -> Optional[tuple[str, str]]:
    """Retourne (filename, extracted_text) ou None si introuvable."""
    if not doc_id:
        return None
    doc = db.get(Document, doc_id)
    if doc is None:
        return None
    return doc.filename, doc.extracted_text or ""


def _scope_doc_ids(session: SessionRow) -> list[uuid.UUID]:
    try:
        raw = json.loads(session.scope_doc_ids or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    out: list[uuid.UUID] = []
    for s in raw:
        try:
            out.append(uuid.UUID(s))
        except (ValueError, TypeError):
            continue
    return out


def _history(db: Session, session: SessionRow, limit: int = 8) -> list[dict[str, str]]:
    msgs = list(session.messages)[-limit:]
    return [{"role": m.role, "content": m.content} for m in msgs if m.role in ("user", "assistant")]


def build_messages(
    db: Session,
    session: SessionRow,
    question: str,
    mistral: MistralClient,
    history: Optional[list[dict[str, str]]] = None,
    k: int = 12,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retourne `(messages_pour_mistral, citations)`.

    Scope :
      - `session.scope_doc_ids` vide → recherche sur tous les documents
      - sinon → restreint aux doc UUIDs listés
    """
    doc_ids = _scope_doc_ids(session)
    hits = search_similar(db, doc_ids if doc_ids else None, question, mistral, k=k)
    blocks = [f"[{h['filename']}] (extrait {i + 1})\n{h['text']}" for i, h in enumerate(hits)]
    citations = [
        {"chunk_id": h["chunk_id"], "filename": h["filename"], "score": h["score"]}
        for h in hits
    ]

    context_text = (
        "Extraits pertinents :\n\n"
        + ("\n\n---\n\n".join(blocks) if blocks else "(aucun extrait trouvé)")
    )

    # Style + template optionnels (Document.kind = style / template).
    style = _load_doc_text(db, session.style_doc_id)
    template = _load_doc_text(db, session.template_doc_id)

    # System prompt = base + options (format / longueur / ton).
    base_prompt = system_prompt(session.lang)
    options = _build_options_preamble(session)
    full_system = base_prompt + ("\n\n" + options if options else "")

    # User content : on assemble contexte + (style) + (template) + brief.
    user_parts: list[str] = [f"Contexte :\n{context_text}"]
    if style is not None:
        user_parts.append(
            f"EXEMPLE DE STYLE / SYNTAXE À REPRODUIRE (extrait de [{style[0]}]) :\n{style[1]}"
        )
    if template is not None:
        user_parts.append(
            f"TEMPLATE À REMPLIR (extrait de [{template[0]}]) :\n{template[1]}"
        )
    user_parts.append(f"Brief : {question}")

    messages: list[dict[str, Any]] = [{"role": "system", "content": full_system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": "\n\n".join(user_parts)})
    return messages, citations


async def stream_answer(
    db: Session,
    session: SessionRow,
    question: str,
    mistral: MistralClient,
) -> AsyncIterator[str]:
    history = _history(db, session)
    messages, citations = build_messages(db, session, question, mistral, history=history)

    db.add(Message(session_id=session.id, role="user", content=question, citations="[]"))
    db.commit()

    full_answer = ""
    async for delta in mistral.chat_stream(messages):
        full_answer += delta
        yield delta

    db.add(
        Message(
            session_id=session.id,
            role="assistant",
            content=full_answer,
            citations=json.dumps(citations, ensure_ascii=False),
        )
    )
    db.commit()


def ensure_session_title(db: Session, session: SessionRow, question: str) -> None:
    """Si la session n'a pas de titre, prend les 60 premiers caractères de la question."""
    if session.title:
        return
    title = question[:60] + ("…" if len(question) > 60 else "")
    session.title = title
    db.commit()
