"""Classification du contexte S1000D : descriptif vs procedural.

C'est l'etage DECISIF : la balise finale depend du contexte, pas de la forme.
Une meme liste a puces -> `randomList` en descriptif, `proceduralStep` en
procedural. (Etape de "type de DM" explicite, en amont de la resolution.)

Strategie :
1. Prior fort = le HINT document fourni a l'upload ("descriptive"/"procedural"
   /"mixed").
2. Heuristique par section : mots-cles de titre + signaux d'action.
3. Raffinement IA (Mistral, optionnel) : si une cle est configuree. Sans cle,
   on reste sur l'heuristique - jamais de crash (degradation gracieuse).
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.core.ir import Context, IRNode
from app.core.mistral_client import (
    MistralClient,
    MistralError,
    get_effective_settings,
    get_llm_enabled,
)

log = logging.getLogger("s1000d_extractor.context")

_PROC_TITLE = re.compile(
    r"\b(remov|install|disassembl|assembl|replac|adjust|test|inspect|servic|repair|"
    r"clean|oil|lubricat|mount|dismount|fit|fill|drain|tighten|loosen|check|"
    r"procedur|maintenanc|operation|depose|repose|demont|mont|remplac|reglage|"
    r"controle|verification|nettoyage|lubrification|graissage|vidange)\w*",
    re.IGNORECASE,
)
_IPD_TITLE = re.compile(
    r"\b(illustrated\s+part|parts?\s+data|parts?\s+catalog|ipd|ipc|"
    r"catalogue\s+(?:de\s+)?pieces|nomenclature)\w*",
    re.IGNORECASE,
)
_DESC_TITLE = re.compile(
    r"\b(descript|general|overview|theory|operation|introduct|purpose|"
    r"generalit|presentation|fonctionnement|principe|apercu)\w*",
    re.IGNORECASE,
)
_IMPERATIVE = re.compile(
    r"^\s*(remove|install|disconnect|connect|tighten|loosen|check|ensure|verify|"
    r"apply|set|turn|press|open|close|deposer|reposer|debrancher|brancher|serrer|"
    r"desserrer|verifier|appliquer|regler|ouvrir|fermer)\b",
    re.IGNORECASE,
)


def _section_signal(section: IRNode) -> Context:
    title = section.text or ""
    if _PROC_TITLE.search(title):
        return "procedural"
    if _DESC_TITLE.search(title):
        return "descriptive"
    # Signaux de contenu : items ordonnes + phrases imperatives -> procedural.
    proc_hits = 0
    for n in section.walk():
        if n.kind == "item-sequence" and n.form == "ordered":
            proc_hits += 1
        if n.kind in ("paragraph", "item") and _IMPERATIVE.match(n.text or ""):
            proc_hits += 1
    return "procedural" if proc_hits >= 2 else "unknown"


def _propagate(section: IRNode, ctx: Context) -> None:
    for n in section.walk():
        n.context = ctx


def _hint_default(hint: str) -> Context:
    if hint in ("descriptive", "procedural"):
        return hint  # type: ignore[return-value]
    return "unknown"


def classify(root: IRNode, *, hint: str = "mixed", db: Session | None = None) -> str:
    """Assigne `context` a tous les noeuds et renvoie le type de DM dominant.

    Renvoie "procedural" ou "descriptive" (jamais "unknown" pour le serialiseur,
    qui doit choisir un content-model : on retombe sur le hint puis descriptif).
    """
    default = _hint_default(hint)
    sections = [c for c in root.children if c.kind == "section"]

    for section in sections:
        ctx = _section_signal(section)
        if ctx == "unknown":
            ctx = default if default != "unknown" else "descriptive"
        _propagate(section, ctx)

    # Noeuds hors section (enfants directs de la racine) : prennent le defaut.
    for n in root.children:
        if n.kind != "section" and n.context == "unknown":
            n.context = default if default != "unknown" else "descriptive"

    if db is not None:
        _llm_refine(sections, db)

    return _dominant_dm_type(root, default)


def _dominant_dm_type(root: IRNode, default: Context) -> str:
    proc = sum(1 for n in root.walk() if n.context == "procedural")
    desc = sum(1 for n in root.walk() if n.context == "descriptive")
    if proc == desc:
        return default if default != "unknown" else "descriptive"
    return "procedural" if proc > desc else "descriptive"


def _llm_refine(sections: list[IRNode], db: Session) -> None:
    """Raffine la classification par section via Mistral (best-effort)."""
    if not get_llm_enabled(db):
        return
    if not get_effective_settings(db).get("api_key"):
        return
    try:
        client = MistralClient.from_db(db)
    except MistralError:
        return
    listing = [
        {"i": i, "title": s.text[:120], "sample": _first_text(s)[:200]}
        for i, s in enumerate(sections)
    ]
    if not listing:
        return
    prompt = (
        "Tu classes des sections de documentation technique aeronautique en "
        "'descriptive' (description/fonctionnement) ou 'procedural' (procedure "
        "de maintenance, suite d'actions). Reponds STRICTEMENT en JSON : "
        '{"labels": [{"i": 0, "context": "descriptive|procedural"}, ...]}.\n\n'
        f"Sections : {listing}"
    )
    try:
        out = client.chat_json([{"role": "user", "content": prompt}], timeout=30.0)
        for lab in out.get("labels", []):
            i = lab.get("i")
            ctx = lab.get("context")
            if isinstance(i, int) and 0 <= i < len(sections) and ctx in ("descriptive", "procedural"):
                _propagate(sections[i], ctx)  # type: ignore[arg-type]
    except (MistralError, Exception) as exc:
        log.warning("LLM context refine skipped: %s", exc)


def _first_text(section: IRNode) -> str:
    for n in section.walk():
        if n.kind in ("paragraph", "item") and n.text:
            return n.text
    return ""


# --- Typage par Data Module (wizard etape 3) --------------------------------

DM_TYPES = ("descriptive", "procedural", "ipd")


def _dm_signal(title: str, root: IRNode, default: Context) -> str:
    if _IPD_TITLE.search(title):
        return "ipd"
    if _PROC_TITLE.search(title):
        return "procedural"
    if _DESC_TITLE.search(title):
        return "descriptive"
    proc_hits = 0
    for n in root.walk():
        if n.kind == "item-sequence" and n.form == "ordered":
            proc_hits += 1
        if n.kind in ("paragraph", "item") and _IMPERATIVE.match(n.text or ""):
            proc_hits += 1
    if proc_hits >= 2:
        return "procedural"
    return default if default != "unknown" else "descriptive"


def guess_dm_type(title: str, root: IRNode) -> str:
    """Type heuristique (sans IA) d'un DM - utilise apres une edition manuelle
    du decoupage (fusion / scission), pour re-proposer un type coherent."""
    ctx = _dm_signal(title, root, "unknown")
    return ctx


def classify_dms(dms: list, *, hint: str = "mixed", db: Session | None = None) -> dict[str, str]:
    """Type chaque DM independamment (descriptive / procedural / ipd) et
    propage le contexte a ses noeuds. Renvoie {dm_id: dm_type}."""
    default = _hint_default(hint)
    types = {dm.dm_id: _dm_signal(dm.title, dm.root, default) for dm in dms}

    if db is not None:
        _llm_refine_dms(dms, types, db)

    for dm in dms:
        ctx: Context = "procedural" if types[dm.dm_id] == "procedural" else "descriptive"
        for n in dm.root.walk():
            n.context = ctx
    return types


def _llm_refine_dms(dms: list, types: dict[str, str], db: Session) -> None:
    if not get_llm_enabled(db):
        return
    if not get_effective_settings(db).get("api_key"):
        return
    try:
        client = MistralClient.from_db(db)
    except MistralError:
        return
    listing = [{"id": dm.dm_id, "title": dm.title[:120], "sample": _first_text(dm.root)[:200]} for dm in dms]
    if not listing:
        return
    prompt = (
        "Classe chaque module de documentation technique aeronautique en "
        "'descriptive' (description/fonctionnement), 'procedural' (procedure de "
        "maintenance, suite d'actions) ou 'ipd' (catalogue de pieces illustre). "
        'Reponds STRICTEMENT en JSON : {"types": [{"id": "dm1", "type": "..."}]}.\n\n'
        f"Modules : {listing}"
    )
    try:
        out = client.chat_json([{"role": "user", "content": prompt}], timeout=30.0)
        for lab in out.get("types", []):
            did, t = lab.get("id"), lab.get("type")
            if did in types and t in DM_TYPES:
                types[did] = t
    except (MistralError, Exception) as exc:
        log.warning("LLM DM typing skipped: %s", exc)
