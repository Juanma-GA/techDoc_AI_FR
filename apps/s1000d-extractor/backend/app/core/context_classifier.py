"""Classification du contexte S1000D : descriptif vs procedural.

C'est l'etage DECISIF : la balise finale depend du contexte, pas de la forme.
Une meme liste a puces -> `randomList` en descriptif, `proceduralStep` en
procedural. (Etape de "type de DM" explicite, en amont de la resolution.)

Strategie :
1. Prior fort = le HINT document fourni a l'upload ("descriptive"/"procedural"
   /"mixed").
2. Heuristique par section : mots-cles de titre + signaux d'action.
3. Le type dominant est choisi a partir des contextes deterministes.
"""

from __future__ import annotations

import re

from app.core.ir import Context, IRNode

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


def classify(root: IRNode, *, hint: str = "mixed") -> str:
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

    return _dominant_dm_type(root, default)


def _dominant_dm_type(root: IRNode, default: Context) -> str:
    proc = sum(1 for n in root.walk() if n.context == "procedural")
    desc = sum(1 for n in root.walk() if n.context == "descriptive")
    if proc == desc:
        return default if default != "unknown" else "descriptive"
    return "procedural" if proc > desc else "descriptive"


# --- Typage par Data Module (wizard etape 3) --------------------------------

DM_TYPES = ("descriptive", "procedural", "ipd")


def apply_dm_type(root: IRNode, dm_type: str) -> None:
    """Propagate le type valide du DM vers tous ses noeuds."""
    context: Context = "procedural" if dm_type == "procedural" else "descriptive"
    for node in root.walk():
        node.context = context


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


def classify_dms(dms: list, *, hint: str = "mixed") -> dict[str, str]:
    """Type chaque DM independamment (descriptive / procedural / ipd) et
    propage le contexte a ses noeuds. Renvoie {dm_id: dm_type}."""
    default = _hint_default(hint)
    types = {dm.dm_id: _dm_signal(dm.title, dm.root, default) for dm in dms}

    for dm in dms:
        apply_dm_type(dm.root, types[dm.dm_id])
    return types
