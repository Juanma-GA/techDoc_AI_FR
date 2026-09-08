"""Compile one imported checklist row into a strict CompiledRule."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.compiled_rules import CompiledRule, RuleTarget
from app.core.errors import AppError
from app.core.excel_rules import ParsedRule
from app.core.llm_suggester import call_chat


CHECKLIST_COMPILER_SYSTEM_PROMPT = """Tu es un compilateur de règles de conformité documentaire.
Ta mission est de convertir une règle en langage naturel en une règle JSON exécutable par un backend déterministe.
Tu ne contrôles pas le document. Tu ne décides pas si le document est conforme. Tu transformes uniquement la règle fournie.
Utilise uniquement ces valeurs :
execution: deterministic | manual | unsupported
field: text | page_number | revision_number | revision_date | first_issue_date | copyright_start_year | copyright_end_year | document_type
operator: exists | not_exists | equals | regex | normalized_equals
Si la règle indique explicitement une vérification humaine, utilise manual et renseigne manual_instruction.
Si la règle est ambiguë ou dépasse les field/operator autorisés, utilise unsupported et renseigne compilation_error en nommant précisément ce qui manque.
Ne complète jamais une information absente. Retourne uniquement un JSON valide correspondant au schéma CompiledRule, sans aucun texte hors JSON."""


_REGION_ALIASES = {
    "": "full_page",
    "full_page": "full_page",
    "page": "full_page",
    "header": "header",
    "en-tete": "header",
    "en-tête": "header",
    "entete": "header",
    "body": "body",
    "corps": "body",
    "footer": "footer",
    "pied de page": "footer",
}
_MANUAL_HANDLING = {"manuel", "manual", "humain", "human", "a la main", "à la main"}


def checklist_rule_id(origin_ref: str) -> str:
    digest = hashlib.sha256(origin_ref.encode("utf-8")).hexdigest()[:12].upper()
    return f"CHECKLIST_{digest}"


def compile_checklist_rule(
    db: Session,
    parsed: ParsedRule,
    filename: str,
    *,
    chat: Callable[..., str] | None = None,
) -> CompiledRule:
    origin_ref = f"{filename}:{parsed.sheet}:{parsed.row_number}"
    rule_id = checklist_rule_id(origin_ref)
    normalized_zone = parsed.target_zone.strip().lower()
    region = _REGION_ALIASES.get(normalized_zone)
    target = RuleTarget(page="all", region=region or "full_page")
    expected_manual = parsed.handling in _MANUAL_HANDLING
    zone_instruction = (
        f'La zone "{parsed.target_zone}" ne correspond à aucune region autorisée; '
        "la règle doit être unsupported et nommer cette region manquante."
        if region is None
        else f'Utilise exactement target={{"page":"all","region":"{region}"}}.'
    )
    user_prompt = json.dumps(
        {
            "required_metadata": {
                "id": rule_id,
                "topic": parsed.category or "Checklist",
                "source": "user_checklist",
                "origin_ref": origin_ref,
            },
            "mapped_input": {
                "check": parsed.check,
                "handling": parsed.handling,
                "zone": parsed.target_zone,
                "context": parsed.context,
            },
            "constraints": [
                zone_instruction,
                "Recopie required_metadata sans modification dans la réponse.",
                "Une prise en compte manuelle impose execution=manual.",
            ],
        },
        ensure_ascii=False,
    )
    try:
        response = (chat or call_chat)(db, CHECKLIST_COMPILER_SYSTEM_PROMPT, user_prompt, temperature=0.0)
        rule = CompiledRule.model_validate(json.loads(response))
        if (rule.id, rule.source, rule.origin_ref) != (rule_id, "user_checklist", origin_ref):
            raise ValueError("id, source ou origin_ref ne correspond pas à la ligne importée")
        if region is None and rule.execution != "unsupported":
            raise ValueError(f'region non supportée: "{parsed.target_zone}"')
        if region is not None and rule.target != target:
            raise ValueError("target ne correspond pas à la zone importée")
        if expected_manual and rule.execution != "manual":
            raise ValueError("la prise en compte manuelle exige execution=manual")
        return rule
    except (AppError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return CompiledRule(
            id=rule_id,
            topic=parsed.category or "Checklist",
            execution="unsupported",
            target=target,
            checks=[],
            compilation_error=f"Réponse du compilateur invalide: {exc}",
            source="user_checklist",
            origin_ref=origin_ref,
        )