"""Vérification adversariale des findings LLM (fiabilisation).

Porté de word-reviewer, adapté au pipeline **synchrone** de doc-reviewer et à
sa primitive `llm_suggester.call_chat`. Chaque finding détecté par l'IA (scan
libre / checklist `llm_nl`, code `AI_SCAN`) repasse par un prompt **indépendant**
chargé de le *réfuter* (défaut = non fondé). Vote à la majorité sur N passes ;
ne survivent que les findings non réfutés. Réduit les faux positifs du tier LLM.
**Le déterministe (regex, structural, units, layout) ne passe jamais par ici** :
il est certain par construction.

Robustesse : JSON illisible ou appel Mistral en échec → on GARDE le finding
(on ne réfute jamais à tort) ; budget épuisé → on garde aussi.
"""

from __future__ import annotations

import json

import structlog
from sqlalchemy.orm import Session

from app.checks.raw import RawSuggestion
from app.core.errors import AppError
from app.core.llm_budget import LlmBudget
from app.core.llm_suggester import call_chat

log = structlog.get_logger(__name__)

_SYSTEM = (
    "Tu es un verificateur qualite documentaire aeronautique, severe et sceptique. "
    "On te soumet un signalement de non-conformite sur un extrait. Determine s'il est "
    "REELLEMENT fonde au vu de l'extrait fourni. En cas de doute, considere-le NON fonde. "
    'Reponds STRICTEMENT en JSON : {"refuted": true|false, "confidence": 0.0-1.0}.'
)


def _parse_verdict(text: str) -> bool:
    """True = le signalement est réfuté. JSON illisible → False (on garde)."""
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        obj = json.loads(text[start:end])
        return bool(obj.get("refuted", False))
    except (ValueError, json.JSONDecodeError, TypeError):
        return False


def _refute_once(db: Session, rule_text: str, excerpt: str) -> bool:
    user = (
        f"Regle : {rule_text}\n\nExtrait du document :\n\"\"\"\n{excerpt[:1200]}\n\"\"\"\n\n"
        "Ce signalement de non-conformite est-il reellement fonde ?"
    )
    try:
        out = call_chat(db, _SYSTEM, user, temperature=0.0)
    except AppError as exc:
        log.warning("refute_call_failed", code=exc.code)
        return False  # appel indisponible -> on ne refute pas (garde le finding)
    return _parse_verdict(out)


def survives(
    db: Session,
    finding: RawSuggestion,
    budget: LlmBudget,
    *,
    passes: int = 3,
) -> bool:
    """True si le finding survit à la vérification adversariale.

    `passes` votes indépendants ; réfuté si la majorité stricte réfute. Le
    `rule_text` est le message du finding, l'`excerpt` son texte d'origine.
    """
    rule_text = finding.message or finding.rule_code
    excerpt = finding.original or ""
    if not excerpt.strip():
        return True  # rien a verifier -> on garde
    votes = max(1, int(passes))
    refutations = 0
    casts = 0
    for _ in range(votes):
        if not budget.spend():
            break  # budget epuise -> on garde (tri par la suite)
        if _refute_once(db, rule_text, excerpt):
            refutations += 1
        casts += 1
    if casts == 0:
        return True
    return refutations < (casts / 2 + 0.5)  # majorite stricte pour refuter


def verify_batch(
    db: Session,
    findings: list[RawSuggestion],
    budget: LlmBudget,
    *,
    passes: int = 3,
) -> list[RawSuggestion]:
    """Filtre `findings` : ne garde que ceux qui survivent à la réfutation."""
    kept: list[RawSuggestion] = []
    for f in findings:
        if survives(db, f, budget, passes=passes):
            kept.append(f)
    return kept
