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

SYSTEM_PROMPT_ES = (
    "Eres un asistente de redaccion tecnica. A partir de un brief del usuario y de extractos "
    "de documentos proporcionados, produces un contenido estructurado, factual y completo en "
    "MARKDOWN (titulos, listas, parrafos — sin bloques de codigo salvo si es pertinente).\n"
    "Citas sistematicamente tus fuentes en la forma [nombre_archivo] despues de cada afirmacion "
    "factual basada en un extracto.\n"
    "Si una informacion solicitada en el brief no esta en los extractos, indicalo explicitamente "
    "en lugar de inventarla.\n"
    "No reproduzcas el brief en tu respuesta, entrega directamente el contenido redactado."
)


def system_prompt(lang: str) -> str:
    if lang == "en":
        return SYSTEM_PROMPT_EN
    if lang == "es":
        return SYSTEM_PROMPT_ES
    return SYSTEM_PROMPT_FR


# Variante SANS source : aucun document n'est selectionne dans le scope.
# On NE fait PAS de RAG (sinon on injecterait des extraits d'autres documents
# indexes) et on rédige LIBREMENT a partir du seul brief utilisateur — pas de
# contrainte "uniquement d'apres les extraits", pas de citations obligatoires.
FREEFORM_SYSTEM_PROMPT_FR = (
    "Tu es un assistant de rédaction technique. Tu produis un contenu structuré, "
    "factuel et complet en MARKDOWN (titres, listes, paragraphes — pas de blocs "
    "de code sauf si pertinent), à partir du SEUL brief de l'utilisateur et de "
    "tes connaissances générales.\n"
    "Aucun document source n'est fourni : appuie-toi sur le brief et rédige "
    "directement. Ne réclame pas de sources, n'invente pas de citations "
    "[fichier].\n"
    "Ne reproduis pas le brief dans ta réponse, livre directement le contenu rédigé."
)

FREEFORM_SYSTEM_PROMPT_EN = (
    "You are a technical writing assistant. You produce structured, factual, "
    "complete content in MARKDOWN (headings, lists, paragraphs — no code blocks "
    "unless relevant), from the user's brief ALONE and your general knowledge.\n"
    "No source document is provided: rely on the brief and write directly. Do "
    "not ask for sources, do not invent [file] citations.\n"
    "Do not repeat the brief in your answer, deliver the written content directly."
)

FREEFORM_SYSTEM_PROMPT_ES = (
    "Eres un asistente de redaccion tecnica. Produces un contenido estructurado, "
    "factual y completo en MARKDOWN (titulos, listas, parrafos — sin bloques de "
    "codigo salvo si es pertinente), a partir UNICAMENTE del brief del usuario y "
    "de tus conocimientos generales.\n"
    "No se proporciona ningun documento fuente: apoyate en el brief y redacta "
    "directamente. No pidas fuentes, no inventes citas [archivo].\n"
    "No reproduzcas el brief en tu respuesta, entrega directamente el contenido."
)


def freeform_system_prompt(lang: str) -> str:
    if lang == "en":
        return FREEFORM_SYSTEM_PROMPT_EN
    if lang == "es":
        return FREEFORM_SYSTEM_PROMPT_ES
    return FREEFORM_SYSTEM_PROMPT_FR


# Directive de langue FORTE, prependee au system prompt (priorite absolue).
# Sans elle, le modele suit la langue dominante de l'entree (brief + extraits,
# souvent en francais) et ignore le prompt systeme traduit.
_LANG_DIRECTIVE: dict[str, str] = {
    "fr": (
        "DIRECTIVE DE LANGUE (PRIORITÉ ABSOLUE) : rédige l'INTÉGRALITÉ de ta "
        "réponse en FRANÇAIS, quelle que soit la langue du brief, des extraits "
        "ou des documents fournis. Traduis si nécessaire. Cette règle prime sur "
        "toutes les autres."
    ),
    "en": (
        "LANGUAGE DIRECTIVE (TOP PRIORITY): write your ENTIRE answer in "
        "ENGLISH, regardless of the language of the brief, excerpts or provided "
        "documents. Translate if needed. This rule overrides all others."
    ),
    "es": (
        "DIRECTIVA DE IDIOMA (PRIORIDAD MÁXIMA): redacta TODA tu respuesta en "
        "ESPAÑOL, sin importar el idioma del brief, de los extractos o de los "
        "documentos proporcionados. Traduce si es necesario. Esta regla prevalece "
        "sobre todas las demás."
    ),
}


def lang_directive(lang: str) -> str:
    return _LANG_DIRECTIVE.get((lang or "fr").lower(), _LANG_DIRECTIVE["fr"])


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
    """Retourne (filename, texte) ou None si introuvable.

    Cas particulier : pour les templates, `Document.extracted_text` est
    repurpose comme cache zones JSON par `documents._write_zones_cache`. Si on
    le detecte, on re-parse le fichier depuis le disque pour recuperer le vrai
    contenu du template (sinon writer_engine enverrait le JSON cache a Mistral
    comme s'il etait le contenu, ce qui produit des reponses incoherentes ou
    interminables — le mode 'template' du system prompt essaie alors de
    'remplir' tous les ids du JSON).
    """
    if not doc_id:
        return None
    doc = db.get(Document, doc_id)
    if doc is None:
        return None
    text = doc.extracted_text or ""
    # Heuristique sure : un texte normal de pptx/docx ne commence pas par '{'
    # ET ne contient pas la cle de marquage du cache zones.
    if text.startswith("{") and '"_kind"' in text[:200] and "zones" in text[:200]:
        try:
            from app.parsers import parse_any
            parsed = parse_any(doc.storage_path)
            text = parsed.get("text", "") or ""
        except Exception:  # noqa: BLE001
            text = ""
    return doc.filename, text


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


# Seuil (caracteres) en dessous duquel un scope explicite est passe ENTIER au
# modele plutot que via le RAG top-k. ~6k tokens : large pour un CV.
_FULL_SOURCE_CHAR_BUDGET = 24000


def _scope_full_texts(
    db: Session, doc_ids: list[uuid.UUID]
) -> list[tuple[str, str]]:
    """Si le texte brut total des docs de scope tient dans le budget, retourne
    [(filename, texte_complet)] pour les passer ENTIERS au modele (au lieu du
    RAG top-k). Sinon [] -> on retombe sur la recherche par similarite.

    Vise les sources courtes (CV typiquement) ou la troncature RAG fait rater
    des infos eparses que la similarite au brief ne remonte pas (langues et
    niveaux en marge, dates de missions, intitules de diplomes).
    """
    loaded: list[tuple[str, str]] = []
    total = 0
    for doc_id in doc_ids:
        item = _load_doc_text(db, doc_id)
        if not item:
            continue
        filename, text = item
        text = (text or "").strip()
        if not text:
            continue
        loaded.append((filename, text))
        total += len(text)
        if total > _FULL_SOURCE_CHAR_BUDGET:
            return []  # trop long -> on garde le RAG
    return loaded


def _history(db: Session, session: SessionRow, limit: int = 8) -> list[dict[str, str]]:
    msgs = list(session.messages)[-limit:]
    return [{"role": m.role, "content": m.content} for m in msgs if m.role in ("user", "assistant")]


def _build_freeform_messages(
    db: Session,
    session: SessionRow,
    question: str,
    history: Optional[list[dict[str, str]]] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Messages pour le cas SANS source : rédaction libre depuis le seul brief.

    Pas de bloc "Extraits pertinents" (aucune source) ni de citations. Le style
    et le template restent injectables s'ils sont attachés à la session. Renvoie
    `(messages, [])` — aucune citation possible sans source.
    """
    base_prompt = freeform_system_prompt(session.lang)
    options = _build_options_preamble(session)
    full_system = (
        lang_directive(session.lang)
        + "\n\n"
        + base_prompt
        + ("\n\n" + options if options else "")
    )

    style = _load_doc_text(db, session.style_doc_id)
    template = _load_doc_text(db, session.template_doc_id)

    user_parts: list[str] = [lang_directive(session.lang)]
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
    return messages, []


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
      - `session.scope_doc_ids` vide → AUCUNE source : génération LIBRE à partir
        du seul brief (pas de RAG, pas de contrainte d'extraits). Évite d'injecter
        des extraits d'autres documents indexés que l'utilisateur n'a pas choisis.
      - sinon → restreint aux doc UUIDs listés (RAG ou texte entier).
    """
    doc_ids = _scope_doc_ids(session)

    # Aucune source selectionnee -> on rédige librement depuis le brief. On
    # n'appelle pas search_similar (qui, sans filtre, balaierait TOUS les docs
    # indexes) et on utilise le prompt systeme "freeform" (sans citations ni
    # contrainte d'extraits). Style/template optionnels restent injectables.
    if not doc_ids:
        return _build_freeform_messages(db, session, question, history)

    # Scope explicite + source courte -> on passe le(s) DOCUMENT(S) ENTIER(S)
    # au lieu du top-k RAG : rien n'est rate (langues, dates) que la similarite
    # au brief aurait pu laisser hors des k extraits. Sinon -> RAG classique.
    scope_full = _scope_full_texts(db, doc_ids) if doc_ids else []
    if scope_full:
        blocks = [f"[{fn}] (document complet)\n{txt}" for fn, txt in scope_full]
        citations = [
            {"chunk_id": "", "filename": fn, "score": 1.0} for fn, _ in scope_full
        ]
    else:
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

    # System prompt = directive de langue (priorite absolue) + base + options.
    base_prompt = system_prompt(session.lang)
    options = _build_options_preamble(session)
    full_system = (
        lang_directive(session.lang)
        + "\n\n"
        + base_prompt
        + ("\n\n" + options if options else "")
    )

    # User content : on assemble contexte + (style) + (template) + brief. Le
    # rappel de langue est place EN TETE pour fixer la langue de sortie avant
    # que le modele ne s'imprime de la langue (souvent FR) du brief/extraits.
    user_parts: list[str] = [lang_directive(session.lang), f"Contexte :\n{context_text}"]
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
