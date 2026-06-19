"""Segmentation de la forme implicite : prose continue -> etapes.

Sujet difficile #2 : en contexte procedural, une suite d'actions est parfois
ecrite en un seul paragraphe ("First... then... finally...") plutot qu'en
liste. Le regex seul echoue ; on combine une heuristique de marqueurs de
sequence et un raffinement IA optionnel (Mistral).

Perf : les appels LLM sont synchrones et sequentiels. Pour ne pas figer
l'extraction sur un gros document, on :
- ne sollicite le LLM QUE pour les paragraphes qui ressemblent vraiment a une
  suite de plusieurs actions (`_looks_multi_action`) - un paragraphe mono-action
  devient une seule etape, sans appel ;
- plafonne le nombre d'appels (`_MAX_LLM_SPLITS`) ;
- utilise un timeout court ; un echec retombe en silence sur l'heuristique.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.ir import IRNode
from app.core.mistral_client import (
    MistralClient,
    MistralError,
    get_effective_settings,
    get_llm_enabled,
)

log = logging.getLogger("s1000d_extractor.segment")

_MAX_LLM_SPLITS = 15      # plafond d'appels LLM de decoupage par document
_LLM_TIMEOUT = 30.0       # timeout court : pas de gel de 2 min sur un appel lent

# Marqueurs de sequence FR + EN.
_SEQ_SPLIT = re.compile(
    r"(?:^|\.\s+|;\s+)(?=(?:first|second|third|then|next|after that|finally|"
    r"d'abord|ensuite|puis|enfin|apres)\b)",
    re.IGNORECASE,
)
_IMPERATIVE = re.compile(
    r"\b(remove|install|disconnect|connect|tighten|loosen|check|ensure|verify|"
    r"apply|set|turn|press|open|close|deposer|reposer|debrancher|brancher|serrer|"
    r"desserrer|verifier|appliquer|regler|ouvrir|fermer)\b",
    re.IGNORECASE,
)


def _heuristic_split(text: str) -> list[str]:
    parts = [p.strip(" .;") for p in _SEQ_SPLIT.split(text) if p.strip(" .;")]
    return parts if len(parts) >= 2 else []


def _looks_multi_action(text: str) -> bool:
    """Vrai si le paragraphe ressemble a PLUSIEURS actions (donc a decouper).

    Un paragraphe mono-action (une seule phrase imperative courte) ne doit pas
    declencher d'appel LLM : il devient une etape unique telle quelle.
    """
    sentences = [s for s in re.split(r"[.;]\s+", text) if len(s.strip()) > 3]
    verbs = len(_IMPERATIVE.findall(text))
    return len(sentences) >= 2 or verbs >= 2 or len(text) > 240


def _make_steps(node: IRNode, steps: list[str]) -> None:
    """Transforme un paragraphe en sequence d'items (etapes) low-confidence."""
    node.kind = "item-sequence"
    node.form = "ordered"
    node.confidence = 0.4
    base = node.id
    node.text = ""
    node.children = [
        IRNode(id=f"{base}s{i}", kind="item", form="ordered", text=s,
               context=node.context, confidence=0.4)
        for i, s in enumerate(steps, start=1)
    ]


def segment(
    root: IRNode,
    *,
    db: Session | None = None,
    progress_cb: Callable[[int], None] | None = None,
) -> int:
    """Decoupe les paragraphes proceduraux en etapes. Renvoie le nb de splits.

    `progress_cb(pct)` (optionnel) est appele entre 60 et 74 pour faire avancer
    la barre pendant les appels LLM successifs.
    """
    use_llm = (
        db is not None
        and get_llm_enabled(db)
        and bool(get_effective_settings(db).get("api_key"))
    )
    client = None
    if use_llm:
        try:
            client = MistralClient.from_db(db)  # type: ignore[arg-type]
        except MistralError:
            client = None

    # Cibles : paragraphes proceduraux qui ressemblent a plusieurs actions.
    targets = [
        n for n in root.walk()
        if n.kind == "paragraph" and n.context == "procedural"
        and len(n.text) >= 60 and _looks_multi_action(n.text)
    ]

    count = 0
    llm_calls = 0
    for i, node in enumerate(targets):
        steps = _heuristic_split(node.text)
        if not steps and client is not None and llm_calls < _MAX_LLM_SPLITS:
            llm_calls += 1
            steps = _llm_split(client, node.text)
        if steps:
            _make_steps(node, steps)
            count += 1
        if progress_cb and targets:
            progress_cb(60 + int(14 * (i + 1) / len(targets)))

    if use_llm and len(targets) > _MAX_LLM_SPLITS:
        log.warning(
            "form_segmenter: %d paragraphes candidats, plafonne a %d appels LLM.",
            len(targets), _MAX_LLM_SPLITS,
        )
    return count


def _llm_split(client: MistralClient, text: str) -> list[str]:
    prompt = (
        "Decoupe ce paragraphe de maintenance en etapes d'action atomiques et "
        "ordonnees. Si ce n'est pas une suite d'actions, renvoie une liste vide. "
        'Reponds STRICTEMENT en JSON : {"steps": ["...", "..."]}.\n\n' + text
    )
    try:
        out = client.chat_json([{"role": "user", "content": prompt}], timeout=_LLM_TIMEOUT)
        steps = [s.strip() for s in out.get("steps", []) if isinstance(s, str) and s.strip()]
        return steps if len(steps) >= 2 else []
    except (MistralError, Exception) as exc:
        log.warning("LLM step split skipped: %s", exc)
        return []
