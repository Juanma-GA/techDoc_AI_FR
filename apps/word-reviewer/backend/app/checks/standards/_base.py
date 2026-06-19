"""Dataclass partagee pour les regles de standard builtin.

`StandardRule` est la representation Python d'une entree de regle. Le seed
serialise une liste de `StandardRule.as_dict()` dans
`standard_versions.catalog_json` : la DB devient la source de verite et
l'utilisateur peut cloner/surcharger une entree via l'API.

Kinds supportes (cf. `app.checks.runner`) :
- texte    : regex_flag, regex_replace, term_replace, case_capitalize, accent_fix
- structurel : field_required, section_required, field_consistency, step_pattern,
  enum_value
- mise en page : style_check (alignement), zone_field (footer/header/zone...)
- revision : revision_check
- manuel / llm : manual, llm_nl

`metadata` porte les options specifiques (ex. `{"zone": "footer", "mode": "forbid"}`
pour un `zone_field`, `{"align": "justify"}` pour un `style_check`).
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
