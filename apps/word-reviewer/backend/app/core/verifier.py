"""Verification adversariale des findings LLM (couche 1 de fiabilisation).

Chaque finding repasse par un prompt **independant** charge de le *refuter*
(defaut = non fonde). Pour un finding `error`, vote a la majorite sur N refuteurs ;
sinon 1 passage. Ne survivent que les findings non refutes. Reduit les faux
positifs du tier LLM. Le deterministe ne passe jamais par ici.
"""

from __future__ import annotations

import json
import logging

from app.checks.raw import RawSuggestion
from app.core.llm_budget import LlmBudget
from app.core.mistral_client import MistralClient

log = logging.getLogger("word_reviewer.verifier")

_SYSTEM = (
    "Tu es un verificateur qualite documentaire aeronautique, severe et sceptique. "
    "On te soumet un signalement de non-conformite. Determine s'il est REELLEMENT "
    "fonde au vu de l'extrait. En cas de doute, considere-le NON fonde. "
    "Reponds uniquement en JSON : {\"refuted\": true|false, \"confidence\": 0.0-1.0}."
)


def _parse_verdict(text: str) -> tuple[bool, float]:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        obj = json.loads(text[start:end])
        return bool(obj.get("refuted", False)), float(obj.get("confidence", 0.5))
    except (ValueError, json.JSONDecodeError, TypeError):
        return False, 0.0  # illisible -> on GARDE le finding (ne pas refuter a tort)


async def _refute_once(client: MistralClient, rule_text: str, excerpt: str) -> bool:
    user = (
        f"Regle : {rule_text}\n\nExtrait du document :\n\"\"\"\n{excerpt[:1200]}\n\"\"\"\n\n"
        "Ce signalement de non-conformite est-il reellement fonde ?"
    )
    try:
        out = await client.chat(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
            temperature=0.0,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("refute call failed: %s", exc)
        return False  # appel echoue -> on ne refute pas (garde le finding)
    refuted, _conf = _parse_verdict(out)
    return refuted


async def survives(
    client: MistralClient,
    finding: RawSuggestion,
    rule_text: str,
    excerpt: str,
    budget: LlmBudget,
) -> bool:
    """True si le finding survit a la verification adversariale."""
    votes = 3 if finding.severity == "error" else 1
    refutations = 0
    casts = 0
    for _ in range(votes):
        verdict = await budget.run(lambda: _refute_once(client, rule_text, excerpt))
        if verdict is None:  # budget epuise
            break
        casts += 1
        if verdict:
            refutations += 1
    if casts == 0:
        return True  # pas pu verifier -> on garde (sera trie par la confiance)
    return refutations < (casts / 2 + 0.5)  # majorite stricte pour refuter
