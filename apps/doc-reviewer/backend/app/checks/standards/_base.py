"""Shared dataclass for built-in standard rules.

`StandardRule` is the in-Python representation of a rule entry. The
Alembic seed serialises a list of `StandardRule.as_dict()` payloads into
`standard_versions.catalog_json` so runtime no longer depends on
Python-side imports — the DB is the source of truth and the user can
clone/override individual entries through the API.

Supported `kind` values mix textual (regex_replace, regex_flag,
term_replace, case_capitalize, accent_fix), structural checks
(field_required, section_required, field_consistency, step_pattern,
enum_value) and style checks (sentence_length — longueur de phrase,
seuil de mots porté par `pattern`). See `app.checks.structural_checks`
and `app.checks.style_checks` for the runtimes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class StandardRule:
    code: str
    title: str
    description: str
    kind: str
    severity: str = "warning"
    pattern: str = ""
    replacement: str = ""
    message: str = ""
    example_invalid: str = ""
    example_valid: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
