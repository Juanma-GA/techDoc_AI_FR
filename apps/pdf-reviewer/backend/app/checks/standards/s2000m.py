"""S2000M (ASD/AIA Material Management) catalog — issue 7.

Standard de gestion des matériels et rechanges. Couvre nomenclature,
codes de maintenance, listes de pièces.
"""

from __future__ import annotations

from app.checks.standards._base import StandardRule


_RULES_ISSUE7 = [
    StandardRule(
        code="S2K_FIELD_NSN",
        title="NSN renseigné",
        description=(
            "Le NATO Stock Number (NSN, 13 chiffres) doit accompagner "
            "chaque article géré sous S2000M."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"\bNSN\b|\b\d{4}-\d{2}-\d{3}-\d{4}\b",
        message="Article sans NSN — référence S2000M incomplète.",
    ),
    StandardRule(
        code="S2K_FIELD_PARTNUMBER",
        title="Part Number obligatoire",
        description="Toute pièce listée doit exposer son Part Number (PN).",
        kind="field_required",
        severity="error",
        pattern="Part Number|P/N|Référence pièce",
        message="Champ « Part Number » manquant.",
    ),
    StandardRule(
        code="S2K_FIELD_CAGE",
        title="CAGE Code renseigné",
        description=(
            "Le CAGE Code (5 caractères) identifie le fournisseur — "
            "obligatoire pour toute pièce gérée S2000M."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"\bCAGE\b|\b[A-Z0-9]{5}\b",
        message="CAGE Code manquant ou format invalide.",
    ),
    StandardRule(
        code="S2K_MAINT_CODE",
        title="Code de maintenance (SMR) valide",
        description=(
            "Le code SMR (Source/Maintenance/Recoverability) doit être "
            "conforme à la grille S2000M (6 caractères)."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"\bSMR\s*[:=]?\s*[A-Z]{6}\b",
        message="Code SMR — vérifier la conformité (6 caractères alpha).",
    ),
    StandardRule(
        code="S2K_FIELD_UNIT_OF_ISSUE",
        title="Unité de gestion renseignée",
        description=(
            "Unit of Issue (UI) obligatoire : EA, KG, L, M, BX, etc."
        ),
        kind="enum_value",
        severity="warning",
        pattern="EA,KG,L,M,BX,PR,SE,ST",
        message="Unité de gestion manquante ou non standard.",
        metadata={"field_label": "Unit of Issue"},
    ),
    StandardRule(
        code="S2K_SECTION_NOMENCLATURE",
        title="Nomenclature article présente",
        description=(
            "Description courte (40 car max) en anglais technique, "
            "obligatoire."
        ),
        kind="section_required",
        severity="warning",
        pattern="Nomenclature|Item Name|Designation",
        message="Section « Nomenclature » absente.",
    ),
    StandardRule(
        code="S2K_SECTION_INTERCHANGE",
        title="Interchangeabilité documentée",
        description=(
            "Toute pièce avec alternatives doit lister les "
            "interchangeabilités (one-way / two-way)."
        ),
        kind="section_required",
        severity="info",
        pattern="Interchangeabilité|Interchangeability|Substitute",
        message="Section « Interchangeabilité » absente.",
    ),
    StandardRule(
        code="S2K_FIELD_SHELF_LIFE",
        title="Durée de vie / péremption",
        description=(
            "Pour les consommables (huiles, joints, adhésifs), la durée "
            "de vie / date de péremption doit être renseignée."
        ),
        kind="field_required",
        severity="warning",
        pattern="Shelf life|Durée de vie|Péremption|Expiration",
        message="Champ « Shelf life » manquant pour un consommable.",
        metadata={"conditional": "item_type=consumable"},
    ),
    StandardRule(
        code="S2K_FIELD_QUANTITY",
        title="Quantité par assemblage (QPA)",
        description=(
            "Le Quantity Per Assembly (QPA) doit être indiqué pour "
            "chaque pièce d'une nomenclature."
        ),
        kind="field_required",
        severity="warning",
        pattern="QPA|Quantity Per Assembly|Quantité par",
        message="Champ « QPA » manquant.",
    ),
    StandardRule(
        code="S2K_NO_PROPRIETARY_MARK",
        title="Marques déposées à neutraliser",
        description=(
            "Les noms commerciaux doivent être annotés (® / ™) ou "
            "remplacés par la désignation générique."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"\b(?:Loctite|Teflon|Velcro|Kevlar)\b(?![®™])",
        message="Marque commerciale sans annotation ®/™.",
    ),
    StandardRule(
        code="S2K_FIELD_HAZMAT",
        title="Classification HAZMAT",
        description=(
            "Tout article dangereux (HAZMAT) doit porter sa "
            "classification ONU/UN code."
        ),
        kind="regex_flag",
        severity="warning",
        pattern=r"\bUN\s*\d{4}\b",
        message="Vérifier la présence d'un UN code pour les HAZMAT.",
    ),
    StandardRule(
        code="S2K_TERMINOLOGY_RECHANGE",
        title="Terminologie « rechange » homogène",
        description=(
            "Préférer « Spare Part » (anglais) ou « Rechange » (français), "
            "éviter les synonymes ambigus."
        ),
        kind="term_replace",
        severity="info",
        pattern=r"\b(?:Replacement part|Substitute|Pi[èe]ce d[eu] rechange)\b",
        replacement="Rechange",
        message="Terminologie rechange — uniformiser.",
    ),
]


CATALOG: dict[str, list[StandardRule]] = {
    "issue 7": _RULES_ISSUE7,
}
