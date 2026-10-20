"""Client-rule presentation for the built-in ASD-STE100 catalog."""

from __future__ import annotations

from app.checks.client_bundle import ClientRuleDefinition
from app.checks.standards import ste100

_ENGLISH_NAMES = {
    "STE_LONG_SENTENCE": "Sentence too long",
    "STE_PASSIVE_VOICE": "Passive voice",
    "STE_FIRST_PERSON": "First person",
    "STE_PROCEDURAL_GERUND": "Gerund at the start of a procedure",
    "STE_VOCAB_NON_APPROVED": "Non-approved vocabulary",
    "STE_NO_MAYBE": "Vague modal",
    "STE_NO_CONTRACTION": "Contraction",
}

_RULES = ste100.CATALOG["issue 7"]
RULE_DEFINITIONS = tuple(
    ClientRuleDefinition(
        compiled_rule=rule,
        name=rule.topic,
        description=str(ste100.RULE_METADATA[rule.id]["description"]),
        message=str(ste100.RULE_METADATA[rule.id]["message"]),
        kind=str(ste100.RULE_METADATA[rule.id]["kind"]),
        presentation_severity=str(ste100.RULE_METADATA[rule.id]["severity"]),
        translations={
            "en": {
                "name": _ENGLISH_NAMES[rule.id],
                "description": str(
                    ste100.RULE_METADATA[rule.id]["description_en"]
                ),
                "message": str(ste100.RULE_METADATA[rule.id]["message_en"]),
            }
        },
    )
    for rule in _RULES
)

STANDARD_SPEC: dict[str, object] = {
    "code": "ASD-STE100",
    "label": "ASD-STE100 — Simplified Technical English",
    "description": (
        "ASD-STE100 issue 7 English writing-style checks for technical documentation."
    ),
    "versions": ste100.CATALOG,
    "metadata": ste100.RULE_METADATA,
}
