from __future__ import annotations

from functools import partial

from app.checks.thales_rules.rule_factory import build_rule
from app.core.compiled_rules import Check, RuleTarget

_ALL_PAGE_TARGET = RuleTarget(page="all", region="full_page")
_rule = partial(build_rule, "THALES-CUSTOM", "v1")

CUSTOM_LEP_PAGE_COLUMN_ALIGNMENT = _rule(
    code="CUSTOM_LEP_PAGE_COLUMN_ALIGNMENT",
    name="Alignement vertical des pages dans la colonne PAGE de la LEP",
    description=(
        "Les numeros de page de chaque colonne PAGE de la LEP doivent etre "
        "alignes verticalement entre eux, a 4 pt pres."
    ),
    message="Les numeros de page de la LEP ne sont pas alignes verticalement.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="ata100_lep_page_column_alignment",
        )
    ],
    failure_message="Aligner verticalement les valeurs de la colonne PAGE de la LEP.",
    translations={
        "en": {
            "description": (
                "Page numbers in each LEP PAGE column must align vertically with "
                "one another, within 4 pt."
            ),
            "message": "The LEP page numbers are not vertically aligned.",
        }
    },
)

CUSTOM_MATERIALS_TABLE_NO_NOTE = _rule(
    code="CUSTOM_MATERIALS_TABLE_NO_NOTE",
    name="Aucune NOTE dans les tableaux materiaux, consommables et equipements",
    description=(
        "Aucune mention NOTE ne doit apparaitre a l'interieur des tableaux des "
        "sections LIST OF MATERIALS, LIST OF CONSUMABLES, SPECIAL TOOLS ou "
        "SPECIAL EQUIPMENT AND TOOLING. Une NOTE placee avant le tableau est admise."
    ),
    message="Une NOTE est presente dans un tableau de materiaux ou consommables.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="ata100_materials",
            operation_params={"control": "no_notes_in_tables"},
        )
    ],
    failure_message="Retirer la NOTE du tableau de materiaux, consommables ou equipements.",
    translations={
        "en": {
            "description": (
                "No NOTE may appear inside a table in the LIST OF MATERIALS, "
                "LIST OF CONSUMABLES, SPECIAL TOOLS, or SPECIAL EQUIPMENT AND "
                "TOOLING sections. A NOTE placed before the table is allowed."
            ),
            "message": "A NOTE appears inside a materials or consumables table.",
        }
    },
)

CUSTOM_LIST_OF_MATERIALS_ROW_ALIGNMENT = _rule(
    code="CUSTOM_LIST_OF_MATERIALS_ROW_ALIGNMENT",
    name="Alignement en haut des cellules de la LIST OF MATERIALS",
    description=(
        "Pour chaque article de la LIST OF MATERIALS, le haut de la designation, "
        "du code, du fournisseur et des marques USE doit etre aligne a 4 pt pres."
    ),
    message="Les cellules d'un article de la LIST OF MATERIALS ne sont pas alignees en haut.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="ata100_materials",
            operation_params={"control": "row_alignment"},
        )
    ],
    failure_message=(
        "Aligner en haut la designation, le code, le fournisseur et les marques USE de chaque article."
    ),
    translations={
        "en": {
            "description": (
                "For each LIST OF MATERIALS item, the top of the designation, code, "
                "supplier, and USE marks must align within 4 pt."
            ),
            "message": "A LIST OF MATERIALS item's cells are not top-aligned.",
        }
    },
)

CUSTOM_LIST_OF_MATERIALS_CODE_SUPPLIER_DEFAULTS = _rule(
    code="CUSTOM_LIST_OF_MATERIALS_CODE_SUPPLIER_DEFAULTS",
    name="Valeurs par defaut du code et du fournisseur dans la LIST OF MATERIALS",
    description=(
        "Lorsqu'un article n'a pas de code specifie, la colonne CODE doit contenir "
        "« not specific » et la colonne SUPPLIERS « Commercially available »."
    ),
    message="Les valeurs CODE ou SUPPLIERS par defaut sont absentes.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="ata100_materials",
            operation_params={"control": "code_supplier_defaults"},
        )
    ],
    failure_message=(
        "Pour un code non specifie, renseigner CODE = not specific et SUPPLIERS = Commercially available."
    ),
    translations={
        "en": {
            "description": (
                "When an item has no specified code, the CODE column must contain "
                '"not specific" and the SUPPLIERS column must contain '
                '"Commercially available".'
            ),
            "message": "The default CODE or SUPPLIERS values are missing.",
        }
    },
)

LEP_RULE_DEFINITIONS = (CUSTOM_LEP_PAGE_COLUMN_ALIGNMENT,)
MATERIALS_RULE_DEFINITIONS = (
    CUSTOM_MATERIALS_TABLE_NO_NOTE,
    CUSTOM_LIST_OF_MATERIALS_ROW_ALIGNMENT,
    CUSTOM_LIST_OF_MATERIALS_CODE_SUPPLIER_DEFAULTS,
)
