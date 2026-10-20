"""ASD-STE100 issue 7 catalog, expressed with the existing CompiledRule contract."""

from __future__ import annotations

from app.core.compiled_rules import Check, CompiledRule, RuleTarget

_TARGET = RuleTarget(page="all", region="full_page")
_ORIGIN = "ASD-STE100:issue 7"


def _rule(code: str, topic: str, pattern: str) -> CompiledRule:
    return CompiledRule(
        id=code,
        topic=topic,
        execution="deterministic",
        target=_TARGET,
        checks=[Check(field="text", operator="regex", expected=pattern)],
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:{code}",
    )


_RULES_ISSUE7 = [
    # Sentence length is counted by style_checks, not executed as a regex.
    _rule(
        "STE_LONG_SENTENCE",
        "Phrase trop longue",
        r"(?!)",
    ),
    _rule(
        "STE_PASSIVE_VOICE",
        "Voix passive",
        (
            r"(?i)\b(?:(?:must|shall|should|can|could|will|would|may|might)\s+)?"
            r"(?:is|are|was|were|be|been|being)\s+"
            r"(?:(?:not|never|fully|partly|properly|securely|currently|already)\s+){0,2}"
            r"(?:being\s+)?"
            r"(?:[a-z]{2,}ed|been|built|bought|brought|caught|chosen|cut|done|drawn|"
            r"driven|eaten|fallen|felt|found|given|gone|held|kept|known|left|lost|"
            r"made|paid|put|read|seen|sent|sold|spent|taken|taught|thought|thrown|"
            r"worn|won|broken|frozen|forgotten|hidden|beaten|forbidden|proven|risen|"
            r"ridden|shaken|spoken|stolen|sworn|torn|understood)\b"
        ),
    ),
    _rule(
        "STE_FIRST_PERSON",
        "Première personne interdite",
        r"(?:(?<![\w/.-])I(?![\w/.-])|(?i:\b(?:me|my|mine|myself|we|us|our|ours|ourselves)\b))",
    ),
    _rule(
        "STE_PROCEDURAL_GERUND",
        "Gérondif en début de procédure",
        r"(?im)(?:^|(?<=[.!?]))\s*(?:When|Before|After|While)\s+[A-Za-z]+ing\b",
    ),
    _rule(
        "STE_VOCAB_NON_APPROVED",
        "Vocabulaire non approuvé",
        r"(?i)\b(?:utilize|utilise)\b",
    ),
    _rule(
        "STE_NO_MAYBE",
        "Modal « maybe/peut-être » imprécis",
        r"(?i)\b(?:maybe|perhaps|possibly)\b",
    ),
    _rule(
        "STE_NO_CONTRACTION",
        "Contractions interdites",
        (
            r"(?i)\b(?:"
            r"i['\u2019](?:m|ve|ll|d)|"
            r"(?:you|we|they)['\u2019](?:re|ve|ll|d)|"
            r"(?:he|she|it|that|there|what|who|where|when|why|how|here)['\u2019](?:s|ve|ll|d)|"
            r"let['\u2019]s|y['\u2019]all|"
            r"(?:do|does|did|is|are|was|were|has|have|had|could|should|would|must|"
            r"might|need|ought|dare)n['\u2019]t|"
            r"can['\u2019]t|won['\u2019]t|shan['\u2019]t|ain['\u2019]t"
            r")\b"
        ),
    ),
]


RULE_METADATA = {
    "STE_LONG_SENTENCE": {
        "description": (
            "ASD-STE100 §6.4 : maximum 20 mots par étape de procédure et "
            "25 mots par phrase descriptive."
        ),
        "kind": "sentence_length",
        "severity": "warning",
        "pattern": "20",
        "descriptive_max_words": 25,
        "message": "Phrase trop longue — STE100 §6.4 limite à 20-25 mots.",
    },
    "STE_PASSIVE_VOICE": {
        "description": "ASD-STE100 §3.4 impose la voix active dans les procédures.",
        "kind": "regex_flag",
        "severity": "info",
        "message": "Voix passive — préférer la voix active à l'impératif (STE §3.4).",
    },
    "STE_FIRST_PERSON": {
        "description": (
            "ASD-STE100 §3.5 interdit la première personne dans les manuels de maintenance."
        ),
        "kind": "regex_flag",
        "severity": "warning",
        "message": "Première personne — préférer la forme impersonnelle (STE §3.5).",
    },
    "STE_PROCEDURAL_GERUND": {
        "description": "ASD-STE100 §3.3 demande l'impératif pour les procédures.",
        "kind": "regex_flag",
        "severity": "info",
        "message": "Gérondif en début de procédure — réécrire à l'impératif.",
    },
    "STE_VOCAB_NON_APPROVED": {
        "description": "STE100 signale les synonymes courants à éviter.",
        "kind": "term_replace",
        "severity": "info",
        "replacement": "use",
        "message": "STE : préférer « use » à « utilize/utilise ».",
    },
    "STE_NO_MAYBE": {
        "description": "STE100 §6 interdit les modaux ambigus dans les procédures.",
        "kind": "regex_flag",
        "severity": "warning",
        "message": "Modal imprécis — supprimer ou reformuler en consigne ferme.",
    },
    "STE_NO_CONTRACTION": {
        "description": "STE100 §3.7 interdit les contractions.",
        "kind": "regex_flag",
        "severity": "info",
        "message": "Contraction — utiliser la forme complète (STE §3.7).",
    },
}

_ENGLISH_RULE_METADATA: dict[str, tuple[str, str]] = {
    "STE_LONG_SENTENCE": (
        "ASD-STE100 §6.4: maximum 20 words per procedural sentence and 25 words per descriptive sentence.",
        "Sentence too long - STE100 §6.4 limits sentences to 20-25 words.",
    ),
    "STE_PASSIVE_VOICE": (
        "ASD-STE100 §3.4 requires the active voice in procedures.",
        "Passive voice - prefer the active imperative form (STE §3.4).",
    ),
    "STE_FIRST_PERSON": (
        "ASD-STE100 §3.5 forbids the first person in maintenance manuals.",
        "First person - prefer the impersonal form (STE §3.5).",
    ),
    "STE_PROCEDURAL_GERUND": (
        "ASD-STE100 §3.3 requires the imperative form for procedures.",
        "Gerund at the start of a procedure - rewrite in the imperative form.",
    ),
    "STE_VOCAB_NON_APPROVED": (
        "STE100 flags common synonyms that should be avoided.",
        "STE: prefer 'use' to 'utilize'.",
    ),
    "STE_NO_MAYBE": (
        "STE100 §6 forbids ambiguous modals in procedures.",
        "Vague modal - remove it or rewrite as a firm instruction.",
    ),
    "STE_NO_CONTRACTION": (
        "STE100 §3.7 forbids contractions.",
        "Contraction - use the complete form (STE §3.7).",
    ),
}

for _rule_code, (_description_en, _message_en) in _ENGLISH_RULE_METADATA.items():
    RULE_METADATA[_rule_code].update(
        description_en=_description_en,
        message_en=_message_en,
    )


CATALOG: dict[str, list[CompiledRule]] = {"issue 7": _RULES_ISSUE7}
