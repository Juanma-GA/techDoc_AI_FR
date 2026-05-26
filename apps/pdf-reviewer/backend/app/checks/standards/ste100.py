"""ASD-STE100 (Simplified Technical English) catalog — issue 7.

Norme de style d'écriture maintenue par AeroSpace and Defence Industries
Association of Europe : vocabulaire approuvé, voix active, phrases courtes,
première personne interdite, gérondif proscrit en début de procédure.

S1000D *référence* STE100 pour la rédaction du texte, mais les deux normes
sont indépendantes et versionnées séparément (STE100 en est à l'issue 7,
S1000D à la 6.0).
"""

from __future__ import annotations

from app.checks.standards._base import StandardRule


_RULES_ISSUE7 = [
    StandardRule(
        code="STE_LONG_SENTENCE",
        title="Phrase trop longue",
        description=(
            "ASD-STE100 §6.4 : maximum 20 mots par phrase procédurale et 25 mots "
            "par phrase descriptive. Au-delà, la phrase devient ambiguë et "
            "difficile à traduire."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"STE100_LONG_SENTENCE",
        message="Phrase trop longue — STE100 §6.4 limite à 20-25 mots.",
        example_invalid=(
            "When the operator wants to remove the panel he must first ensure "
            "the equipment is fully de-energised and use the dedicated tool."
        ),
        example_valid="De-energise the equipment. Use the dedicated tool to remove the panel.",
    ),
    StandardRule(
        code="STE_PASSIVE_VOICE",
        title="Voix passive",
        description=(
            "ASD-STE100 §3.4 impose la voix active dans les procédures : "
            "« Retirez la vis » plutôt que « La vis doit être retirée »."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"\b(?:is|are|was|were|be|been|being)\s+\w+(?:ed|en)\b",
        message="Voix passive — préférer la voix active à l'impératif (STE §3.4).",
        example_invalid="The screw is to be removed by the operator.",
        example_valid="Remove the screw.",
    ),
    StandardRule(
        code="STE_FIRST_PERSON",
        title="Première personne interdite",
        description=(
            "ASD-STE100 §3.5 : les manuels de maintenance s'adressent à un "
            "opérateur sur un ton neutre. Les pronoms « I », « we », « nous », "
            "« notre » sont prohibés."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"\b(?:I|we|my|our|us|nous|notre|nos|je|mon|ma|mes)\b",
        message="Première personne — préférer la forme impersonnelle (STE §3.5).",
    ),
    StandardRule(
        code="STE_PROCEDURAL_GERUND",
        title="Gérondif en début de procédure",
        description=(
            "ASD-STE100 §3.3 demande l'impératif pour les procédures. Les "
            "gérondifs en début de phrase (« Removing… », « Before opening… ») "
            "ralentissent la lecture et créent des ambiguïtés temporelles."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"(?:^|(?<=[.!?]\s))(?:When|Before|After|While)\s+\w+ing\b",
        message="Gérondif en début de procédure — réécrire à l'impératif.",
        example_invalid="Before opening the panel, ensure the system is off.",
        example_valid="Ensure the system is off. Then open the panel.",
    ),
    StandardRule(
        code="STE_VOCAB_NON_APPROVED",
        title="Vocabulaire non approuvé",
        description=(
            "STE100 maintient un dictionnaire de mots approuvés (~900 mots "
            "techniques). Cette règle signale les synonymes courants à éviter."
        ),
        kind="term_replace",
        severity="info",
        pattern=r"\b(?:utilize|utilise)\b",
        replacement="use",
        message="STE : préférer « use » à « utilize/utilise ».",
    ),
    StandardRule(
        code="STE_NO_MAYBE",
        title="Modal « maybe/peut-être » imprécis",
        description=(
            "STE100 §6 interdit les modaux ambigus dans les procédures. "
            "Préférer une consigne ferme (« Inspect… ») ou un seuil mesurable."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"\b(?:maybe|perhaps|peut-?être|possibly)\b",
        message="Modal imprécis — supprimer ou reformuler en consigne ferme.",
    ),
    StandardRule(
        code="STE_NO_CONTRACTION",
        title="Contractions interdites",
        description=(
            "STE100 §3.7 interdit les contractions (« don't », « can't ») "
            "qui compliquent la lecture des non-anglophones."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"\b(?:don't|can't|won't|isn't|aren't|wasn't|weren't|shouldn't|wouldn't|couldn't|hasn't|haven't|hadn't|doesn't|didn't)\b",
        message="Contraction — utiliser la forme complète (STE §3.7).",
    ),
]


CATALOG: dict[str, list[StandardRule]] = {
    "issue 7": _RULES_ISSUE7,
}
