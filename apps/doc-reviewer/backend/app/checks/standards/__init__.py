"""Built-in catalogs for the supported documentation standards.

Each submodule exports a `CATALOG: dict[version_label, list[StandardRule]]`
mapping a published version to its rule set. The Alembic seed migration
imports `BUILTIN_STANDARDS` to populate the `standards` /
`standard_versions` tables on first boot — runtime reads are then served
from the DB so the user can clone/override built-in catalogs.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Callable

from app.checks.standards import ata100, mat10000, ste100
from app.checks.standards._catalog import serialize_compiled_rule
from app.core.compiled_rules import CompiledRule
from app.parsers.pdf_parser import ParsedPdf


# Le Doc Reviewer analyse le **rendu PDF** publié, jamais la source. Les
# normes purement XML/gestion de données (S1000D, ATA iSpec 2200, S2000M)
# ont été retirées du catalogue : leurs règles vérifiaient des champs/codes
# (DMC, NSN, CAGE, Information Code, SMR, QPA…) qui n'existent que dans le
# XML/SGML source et n'ont pas de sens sur un PDF. Seules restent les normes
# dont les règles portent sur le texte/rendu : ASD-STE100 (style), MAT10000
# (description de tâche) et ATA 100 (chapitrage). Les règles de style
# rédactionnel STE (voix passive, gérondif, longueur de phrase…) vivent dans
# le catalogue ASD-STE100 et sont exécutées par `catalog_runner`
# (+ `style_checks` pour la longueur de phrase).
_BUILTIN_MODULE_NAMES = frozenset({"ata100", "mat10000", "ste100"})


def _discover_custom_standard_modules() -> list[Any]:
    modules: list[Any] = []
    for module_info in pkgutil.iter_modules(__path__):
        module_name = module_info.name
        if module_name.startswith("_") or module_name in _BUILTIN_MODULE_NAMES:
            continue
        module = importlib.import_module(f"{__name__}.{module_name}")
        if isinstance(getattr(module, "STANDARD_SPEC", None), dict):
            modules.append(module)
    return modules


_CUSTOM_STANDARD_MODULES = _discover_custom_standard_modules()
CUSTOM_STANDARD_SPECS: list[dict[str, object]] = [
    module.STANDARD_SPEC for module in _CUSTOM_STANDARD_MODULES
]


BUILTIN_STANDARDS: list[dict[str, object]] = [
    {
        "code": "ASD-STE100",
        "label": "ASD-STE100 — Simplified Technical English",
        "description": (
            "Norme de style d'écriture maintenue par ASD (AeroSpace and "
            "Defence Industries Association of Europe). Vocabulaire "
            "approuvé, voix active, phrases courtes, première personne "
            "interdite, gérondif proscrit. Référencée par S1000D mais "
            "indépendante."
        ),
        "versions": ste100.CATALOG,
        "metadata": ste100.RULE_METADATA,
    },
    {
        "code": "MAT10000",
        "label": "MAT10000 — Maintenance task description (Dassault Aviation)",
        "description": (
            "Référentiel Dassault pour la description des tâches de "
            "maintenance : structure de procédure, ressources requises, "
            "consignes de sécurité."
        ),
        "versions": mat10000.CATALOG,
        "metadata": mat10000.RULE_METADATA,
    },
    {
        "code": "ATA100",
        "label": "ATA 100 — Specification for manufacturers' technical data",
        "description": (
            "Chapitrage standard des manuels techniques aéronautiques "
            "civils (chapitre/section/sujet). Format historique remplacé "
            "par iSpec 2200 mais toujours référencé."
        ),
        "versions": ata100.CATALOG,
        "metadata": ata100.RULE_METADATA,
    },
]
BUILTIN_STANDARDS.extend(
    CUSTOM_STANDARD_SPECS
)

# Optionnel par standard : classe les pages du PDF parse (`page.page_type`) en
# fonction du contexte document, AVANT l'execution des regles compilees, pour
# les standards dont des regles ciblent un `page_type` (cf. RuleTarget). Cle
# = `code` du standard (voir chaque spec ci-dessus) : le pipeline generique
# (`rules_engine.run_all`) n'a donc jamais besoin d'importer un module de
# standard particulier par son nom.
PAGE_CLASSIFIERS: dict[str, Callable[[ParsedPdf, Any], None]] = {
    str(module.STANDARD_SPEC["code"]): classifier
    for module in _CUSTOM_STANDARD_MODULES
    if (classifier := getattr(module, "classify_pages", None)) is not None
    and callable(classifier)
}


def serialize_builtin_version(spec: dict[str, object], label: str) -> list[dict[str, object]]:
    """Serialize a built-in CompiledRule catalog for DB/API compatibility."""
    versions = spec["versions"]
    metadata = spec.get("metadata") or {}
    rules = versions[label]  # type: ignore[index]
    return [
        serialize_compiled_rule(rule, metadata.get(rule.id))  # type: ignore[union-attr]
        for rule in rules  # type: ignore[union-attr]
    ]


def builtin_rule_metadata(code: str) -> dict[str, object]:
    """Return presentation metadata for a built-in compiled rule."""
    for spec in BUILTIN_STANDARDS:
        metadata = spec.get("metadata") or {}
        if code in metadata:
            return dict(metadata[code])  # type: ignore[index]
    return {}


__all__ = ["BUILTIN_STANDARDS", "CompiledRule", "builtin_rule_metadata", "serialize_builtin_version"]
