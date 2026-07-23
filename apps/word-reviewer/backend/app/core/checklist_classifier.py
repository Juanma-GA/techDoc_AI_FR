"""Classification LLM des items de checklist a l'import (couche optionnelle).

`classify_rules(db, rules)` affine la classification heuristique
(`excel_rules.parse_checklist`) via Mistral quand une cle est configuree : un
**seul** appel classe tous les items en lot (kind / zone / severite). Repli
silencieux sur l'heuristique si pas de cle, erreur reseau, ou JSON illisible.
Retourne `(rules, llm_used)`.
"""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from app.core.excel_rules import ParsedRule
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled

log = logging.getLogger("word_reviewer.checklist_classifier")

_KINDS = [
    "regex_flag", "regex_replace", "term_replace", "case_capitalize", "accent_fix",
    "field_required", "section_required", "enum_value", "step_pattern",
    "style_check", "zone_field", "revision_check", "manual", "llm_nl",
]
_ZONES = ["footer", "header", "highlights_table", "fiche_suiveuse", "lep", "title_page", "body", ""]
_SEV = ["info", "warning", "error"]

_PATTERN_REQUIRED = {
    "regex_flag", "regex_replace", "term_replace", "zone_field",
    "section_required", "field_required", "enum_value", "step_pattern",
}
_REGEX_COMPILE = {"regex_flag", "regex_replace", "term_replace", "zone_field", "step_pattern"}

_SYSTEM = (
    "Tu es un expert qualite documentaire aeronautique (manuels CMM). On te donne "
    "des items d'une checklist de revue. Pour CHAQUE item, produis une regle "
    "EXECUTABLE. Choisis le kind et fournis le pattern necessaire :\n"
    "- regex_replace : `pattern` (regex) + `replacement` (peut utiliser \\1, \\2). "
    "Ex 'remplacer AVIONICS/SEXTANT/THOMSON par THALES' -> pattern "
    "'\\\\b(AVIONICS|SEXTANT|THOMSON)\\\\b', replacement 'THALES'.\n"
    "- term_replace : `pattern` = terme(s) (alternation regex), `replacement` = terme correct.\n"
    "- regex_flag : `pattern` (regex) qui repere le probleme (signalement sans correction).\n"
    "- zone_field : `pattern` (regex) que la `zone` DOIT contenir (presence). Ex footer ATA.\n"
    "- section_required / field_required : `pattern` = libelles separes par | qui doivent exister.\n"
    "- style_check : mise en forme (justification) ; pattern et replacement vides.\n"
    "- manual : visuel non automatisable (logo, illustration, barre de revision, OCR, mise en page) ; vides.\n"
    "- llm_nl : verification semantique a confier au LLM ; vides.\n"
    "REGLE D'OR : si tu ne peux pas fournir un pattern FIABLE pour un kind a pattern, "
    "choisis 'llm_nl' (ne laisse JAMAIS un kind deterministe sans pattern).\n"
    "- zone parmi : footer, header, highlights_table, fiche_suiveuse, lep, title_page, body, ou vide.\n"
    "- severity parmi : info, warning, error.\n"
    "Reponds uniquement en JSON : {\"rules\": [{\"i\": <index>, \"kind\": \"...\", "
    "\"zone\": \"...\", \"severity\": \"...\", \"pattern\": \"...\", \"replacement\": \"...\"}]}."
)


def _parse(text: str) -> list[dict]:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        obj = json.loads(text[start:end])
        rules = obj.get("rules", [])
        return rules if isinstance(rules, list) else []
    except (ValueError, json.JSONDecodeError, TypeError):
        return []


async def classify_rules(db: Session, rules: list[ParsedRule]) -> tuple[list[ParsedRule], bool]:
    if not rules:
        return rules, False
    if not get_llm_enabled(db):
        return rules, False
    try:
        client = MistralClient.from_db(db)
    except MistralError:
        return rules, False

    numbered = "\n".join(f"[{i}] {r.name}" for i, r in enumerate(rules))
    user = "Items :\n" + numbered
    try:
        out = await client.chat(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
            temperature=0.0,
            timeout=90.0,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("classification LLM checklist echouee, repli heuristique: %s", exc)
        return rules, False

    applied = False
    for v in _parse(out):
        try:
            if not isinstance(v, dict):
                continue
            i = int(v.get("i"))
        except (TypeError, ValueError):
            continue
        if not (0 <= i < len(rules)):
            continue
        kind = v.get("kind") if v.get("kind") in _KINDS else None
        if not kind:
            continue
        pattern = str(v.get("pattern") or "").strip()
        replacement = str(v.get("replacement") or "").strip()
        # Une regle a pattern sans pattern (ou regex invalide) est inerte :
        # on retombe sur llm_nl qui, lui, fonctionne (evaluation semantique).
        if kind in _PATTERN_REQUIRED:
            if not pattern:
                kind, pattern, replacement = "llm_nl", "", ""
            elif kind in _REGEX_COMPILE:
                try:
                    re.compile(pattern)
                except re.error:
                    kind, pattern, replacement = "llm_nl", "", ""
        rules[i].kind = kind
        rules[i].pattern = pattern
        rules[i].replacement = replacement
        zone = v.get("zone")
        if zone in _ZONES:
            rules[i].target_zone = "" if zone is None else zone
        sev = v.get("severity")
        if sev in _SEV:
            rules[i].severity = sev
        applied = True
    return rules, applied


_SEV_SYSTEM = (
    "Tu es un expert qualite documentaire aeronautique (manuels CMM). On te donne "
    "des items d'une checklist de revue. Pour CHAQUE item, evalue UNIQUEMENT sa "
    "severite au regard de l'impact qualite d'un non-respect :\n"
    "- error : non-conformite bloquante (donnee fausse, exigence reglementaire, "
    "reference/numero errone, incoherence critique).\n"
    "- warning : ecart a corriger sans blocage (formulation, mise en forme, terme).\n"
    "- info : recommandation / point d'attention non bloquant.\n"
    "Ne change RIEN d'autre. Reponds uniquement en JSON : "
    "{\"rules\": [{\"i\": <index>, \"severity\": \"info|warning|error\"}]}."
)


async def classify_severities(db: Session, rules: list[ParsedRule]) -> tuple[list[ParsedRule], bool]:
    """Attribue par IA la SEULE severite (info/warning/error) de chaque item, en un
    unique appel Mistral. Ne touche ni au kind, ni a la zone, ni au pattern.

    A appeler quand la checklist n'a pas de colonne severite : sans elle, l'import
    retombe sur l'heuristique par mots-cles (jamais `error`). Repli silencieux sur
    la severite existante si pas de cle, LLM OFF, erreur reseau ou JSON illisible
    (regle #6). Retourne `(rules, llm_used)`.
    """
    if not rules:
        return rules, False
    if not get_llm_enabled(db):
        return rules, False
    try:
        client = MistralClient.from_db(db)
    except MistralError:
        return rules, False

    numbered = "\n".join(f"[{i}] {r.name}" for i, r in enumerate(rules))
    user = "Items :\n" + numbered
    try:
        out = await client.chat(
            [{"role": "system", "content": _SEV_SYSTEM}, {"role": "user", "content": user}],
            temperature=0.0,
            timeout=90.0,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("severite LLM checklist echouee, repli heuristique: %s", exc)
        return rules, False

    applied = False
    for v in _parse(out):
        try:
            if not isinstance(v, dict):
                continue
            i = int(v.get("i"))
        except (TypeError, ValueError):
            continue
        if not (0 <= i < len(rules)):
            continue
        sev = v.get("severity")
        if sev in _SEV:
            rules[i].severity = sev
            applied = True
    return rules, applied
