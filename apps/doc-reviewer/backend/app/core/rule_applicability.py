"""Central applicability guards used before rule dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DocumentLanguage = Literal["fr", "en"]

_STANDARD_LANGUAGES: dict[str, DocumentLanguage] = {
    "ASD-STE100": "en",
}


@dataclass(frozen=True)
class RuleExecutionContext:
    document_language: DocumentLanguage | None
    layout_enabled: bool = False

    @classmethod
    def from_document(
        cls,
        document: object,
        *,
        layout_enabled: bool = False,
    ) -> RuleExecutionContext:
        raw_language = getattr(document, "document_language", None)
        language = raw_language.strip().lower() if isinstance(raw_language, str) else None
        if language not in {"fr", "en"}:
            language = None
        return cls(document_language=language, layout_enabled=layout_enabled)


def required_language_for_standard(standard_code: str) -> DocumentLanguage | None:
    return _STANDARD_LANGUAGES.get(standard_code.strip().upper())


def is_standard_applicable(
    standard_code: str,
    context: RuleExecutionContext,
) -> bool:
    required_language = required_language_for_standard(standard_code)
    return required_language is None or context.document_language == required_language


def is_rule_kind_applicable(kind: str, context: RuleExecutionContext) -> bool:
    """Return whether a rule kind can safely run in this document context."""
    normalized_kind = kind.strip().lower()
    if normalized_kind == "accent_fix":
        return context.document_language == "fr"
    if normalized_kind == "layout":
        return context.layout_enabled
    return True
