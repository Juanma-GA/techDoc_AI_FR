"""Editable literal equivalents of the original FR/EN requirement patterns."""

from itertools import product, zip_longest
from typing import Literal, TypedDict

Category = Literal["conditions", "personnel", "support", "supplies", "spares", "safety"]
RuleKind = Literal["keyword", "heading"]


class RuleEntry(TypedDict):
    category: Category
    kind: RuleKind
    fr: str
    en: str


def _phrases(prefixes: list[str], names: list[str], suffixes: list[str]) -> list[str]:
    return ["".join(parts) for parts in product(prefixes, names, suffixes)]


KEYWORDS: dict[Category, tuple[list[str], list[str]]] = {
    "conditions": (
        ["avant", "assurer", "prealable", "condition", "hors tension"],
        ["before", "prior to", "ensure", "make sure", "prerequisite", "condition"],
    ),
    "personnel": (
        ["personnel", "technicien", "techniciens", "operateur", "operateurs", "qualification"],
        ["personnel", "technician", "technicians", "operator", "operators", "mechanic", "qualified"],
    ),
    "support": (
        ["outillage", "outil", "outils", "equipement", "cle", "tournevis"],
        ["tool", "tools", "equipment", "wrench", "spanner", "screwdriver"],
    ),
    "supplies": (
        ["consommable", "consommables", "graisse", "solvant", "colle"],
        ["consumable", "consumables", "supply", "supplies", "lubricant", "grease", "solvent", "adhesive"],
    ),
    "spares": (
        ["rechange", "joint neuf"],
        ["spare", "spares", "replacement part", "replacement parts", "new seal", "new gasket"],
    ),
    "safety": (
        ["avertissement", "attention", "danger", "risque", "securite", "protection"],
        ["warning", "caution", "danger", "hazard", "safety", "protective"],
    ),
}

HEADINGS: dict[Category, tuple[list[str], list[str]]] = {
    "conditions": (
        _phrases([""], ["condition", "conditions"],
                 ["", " prealable", " prealables", " requise", " requises", " a respecter"]),
        ["precondition", "preconditions", "prerequisite", "prerequisites",
         "required condition", "required conditions", "condition", "conditions"],
    ),
    "personnel": (
        ["personnel", "personnel requis", "personnel necessaire"],
        _phrases(["", "required ", "qualified "], ["personnel"],
                 ["", " requis", " necessaire"]) + ["manpower"],
    ),
    "support": (
        _phrases([""], ["outillage", "outil", "outils", "equipement", "equipements"],
                 ["", " required", " necessaire", " necessaires", " requis"]),
        _phrases(["", "required ", "special "],
                 ["support equipment", "tool", "tools", "tooling", "equipment",
                  "outillage", "outil", "outils", "equipement", "equipements"],
                 ["", " required", " necessaire", " necessaires", " requis"]),
    ),
    "supplies": (
        _phrases([""], ["fourniture", "fournitures", "consommable", "consommables"], ["", " requis"]),
        _phrases(["", "required "],
                 ["supplies", "consumable", "consumables", "fourniture", "fournitures",
                  "consommable", "consommables"], ["", " required", " requis"]),
    ),
    "spares": (
        _phrases([""], ["piece rechange", "pieces rechange", "piece de rechange", "pieces de rechange"],
                 ["", " requise", " requises"]),
        _phrases(["", "required "],
                 ["spare", "spares", "spare parts", "piece rechange", "pieces rechange",
                  "piece de rechange", "pieces de rechange"], ["", " required", " requise", " requises"]),
    ),
    "safety": (
        ["securite", "precaution", "precautions", "precaution de securite", "precautions de securite"],
        _phrases(["", "general ", "required "], ["safety"],
                 ["", " requirement", " requirements", " precaution", " precautions"])
        + ["security requirement", "security requirements"],
    ),
}


def default_entries() -> list[RuleEntry]:
    entries: list[RuleEntry] = []
    groups_by_kind: dict[RuleKind, dict[Category, tuple[list[str], list[str]]]] = {
        "keyword": KEYWORDS, "heading": HEADINGS,
    }
    for kind, groups in groups_by_kind.items():
        for category, (french, english) in groups.items():
            # Some legacy patterns accepted mixed-language labels. Keep every
            # accepted spelling visible/editable instead of retaining hidden regexes.
            for fr, en in zip_longest(french, english):
                entries.append({
                    "category": category, "kind": kind,
                    "fr": fr if fr is not None else french[0],
                    "en": en if en is not None else english[0],
                })
    return entries
