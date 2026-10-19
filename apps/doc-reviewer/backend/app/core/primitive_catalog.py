"""Closed catalogue of declarative rule primitives and runtime references."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


PrimitiveFamily = Literal[
    "selector",
    "extractor",
    "conversion",
    "reference",
    "assertion",
    "repair",
]
ParameterKind = Literal[
    "string",
    "string_list",
    "regex",
    "replacement",
    "field",
    "reference",
    "region",
    "page",
    "normalization",
]
ValueType = Literal[
    "document",
    "target_set",
    "text",
    "field_value",
    "reference_value",
    "boolean",
    "evidence",
    "finding",
    "patch",
]
ReferenceValueType = Literal["text", "date_text", "year", "language"]
ReferenceSource = Literal["document", "document_text"]


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrimitiveParameter(CatalogModel):
    name: str
    kind: ParameterKind
    required: bool = True
    description: str


class PrimitiveDefinition(CatalogModel):
    id: str
    family: PrimitiveFamily
    input_type: ValueType
    output_type: ValueType
    deterministic: bool
    patchable: bool
    description: str
    parameters: tuple[PrimitiveParameter, ...] = ()


class ReferenceDefinition(CatalogModel):
    id: str
    field: str
    source: ReferenceSource
    value_type: ReferenceValueType
    available_at: Literal["analysis"]
    description: str


REFERENCE_CATALOG: tuple[ReferenceDefinition, ...] = (
    ReferenceDefinition(
        id="document.meta_revision_date",
        field="meta_revision_date",
        source="document",
        value_type="date_text",
        available_at="analysis",
        description="Date de revision saisie pour le document analyse.",
    ),
    ReferenceDefinition(
        id="document.meta_cmm_number",
        field="meta_cmm_number",
        source="document",
        value_type="text",
        available_at="analysis",
        description="Numero CMM saisi pour le document analyse.",
    ),
    ReferenceDefinition(
        id="document.meta_first_issue_date",
        field="meta_first_issue_date",
        source="document",
        value_type="date_text",
        available_at="analysis",
        description="Date de premiere issue saisie pour le document analyse.",
    ),
    ReferenceDefinition(
        id="document.meta_manufacturer",
        field="meta_manufacturer",
        source="document",
        value_type="text",
        available_at="analysis",
        description="Constructeur choisi pour le document analyse (Airbus ou Boeing).",
    ),
    ReferenceDefinition(
        id="document.meta_last_issue_date",
        field="meta_last_issue_date",
        source="document",
        value_type="date_text",
        available_at="analysis",
        description="Date de la revision precedente saisie pour le document analyse.",
    ),
    ReferenceDefinition(
        id="document.meta_revision_number",
        field="meta_revision_number",
        source="document",
        value_type="text",
        available_at="analysis",
        description="Numero de revision saisi pour le document analyse.",
    ),
    ReferenceDefinition(
        id="document.document_language",
        field="document_language",
        source="document",
        value_type="language",
        available_at="analysis",
        description="Langue du document analyse.",
    ),
    ReferenceDefinition(
        id="extracted.revision_number",
        field="revision_number",
        source="document_text",
        value_type="text",
        available_at="analysis",
        description="Numero de revision extrait du texte cible.",
    ),
    ReferenceDefinition(
        id="extracted.revision_date",
        field="revision_date",
        source="document_text",
        value_type="date_text",
        available_at="analysis",
        description="Date de revision extraite du texte cible.",
    ),
    ReferenceDefinition(
        id="extracted.first_issue_date",
        field="first_issue_date",
        source="document_text",
        value_type="date_text",
        available_at="analysis",
        description="Date de premiere issue extraite du texte cible.",
    ),
    ReferenceDefinition(
        id="extracted.copyright_end_year",
        field="copyright_end_year",
        source="document_text",
        value_type="year",
        available_at="analysis",
        description="Annee de fin du copyright extraite du texte cible.",
    ),
)


PRIMITIVE_CATALOG: tuple[PrimitiveDefinition, ...] = (
    PrimitiveDefinition(
        id="select.target",
        family="selector",
        input_type="document",
        output_type="target_set",
        deterministic=True,
        patchable=False,
        description="Selectionne les pages et regions a controler.",
        parameters=(
            PrimitiveParameter(name="page", kind="page", description="Page ou all."),
            PrimitiveParameter(
                name="region",
                kind="region",
                description="full_page, page_without_footer, header, body ou footer.",
            ),
        ),
    ),
    PrimitiveDefinition(
        id="extract.field",
        family="extractor",
        input_type="target_set",
        output_type="field_value",
        deterministic=True,
        patchable=False,
        description="Extrait un champ structure depuis le texte cible.",
        parameters=(
            PrimitiveParameter(name="field", kind="field", description="Champ EntityField autorise."),
        ),
    ),
    PrimitiveDefinition(
        id="convert.normalize",
        family="conversion",
        input_type="field_value",
        output_type="field_value",
        deterministic=True,
        patchable=False,
        description="Applique une suite de normalisations autorisees.",
        parameters=(
            PrimitiveParameter(name="steps", kind="normalization", description="Etapes de normalisation autorisees."),
        ),
    ),
    PrimitiveDefinition(
        id="reference.document",
        family="reference",
        input_type="document",
        output_type="reference_value",
        deterministic=True,
        patchable=False,
        description="Resout une reference du registre au runtime de l'analyse.",
        parameters=(
            PrimitiveParameter(name="reference_id", kind="reference", description="Identifiant du ReferenceDefinition."),
        ),
    ),
    PrimitiveDefinition(
        id="assert.exists",
        family="assertion",
        input_type="text",
        output_type="finding",
        deterministic=True,
        patchable=False,
        description="Verifie la presence d'une valeur litterale dans le texte cible.",
        parameters=(
            PrimitiveParameter(name="expected", kind="string", description="Mention obligatoire exacte."),
        ),
    ),
    PrimitiveDefinition(
        id="assert.not_exists",
        family="assertion",
        input_type="text",
        output_type="finding",
        deterministic=True,
        patchable=False,
        description="Verifie l'absence d'une valeur litterale dans le texte cible.",
        parameters=(
            PrimitiveParameter(name="forbidden", kind="string", description="Mention interdite exacte."),
        ),
    ),
    PrimitiveDefinition(
        id="assert.matches",
        family="assertion",
        input_type="text",
        output_type="finding",
        deterministic=True,
        patchable=False,
        description="Verifie la presence ou l'absence d'un motif variable explicite.",
        parameters=(
            PrimitiveParameter(name="pattern", kind="regex", description="Motif regex Python compile et valide."),
            PrimitiveParameter(name="required", kind="string", description="true pour motif obligatoire, false pour interdit."),
        ),
    ),
    PrimitiveDefinition(
        id="assert.equals_reference",
        family="assertion",
        input_type="field_value",
        output_type="finding",
        deterministic=True,
        patchable=False,
        description="Compare une propriete extraite avec une reference runtime.",
        parameters=(
            PrimitiveParameter(name="reference_id", kind="reference", description="Identifiant de la reference attendue."),
            PrimitiveParameter(name="normalization", kind="normalization", description="Normalisation commune avant comparaison."),
        ),
    ),
    PrimitiveDefinition(
        id="repair.replace_match",
        family="repair",
        input_type="finding",
        output_type="patch",
        deterministic=True,
        patchable=True,
        description="Remplace uniquement une correspondance observee.",
        parameters=(
            PrimitiveParameter(name="replacement", kind="replacement", description="Texte de remplacement explicite."),
        ),
    ),
    PrimitiveDefinition(
        id="repair.replace_capture",
        family="repair",
        input_type="finding",
        output_type="patch",
        deterministic=True,
        patchable=True,
        description="Remplace une correspondance avec des groupes de capture.",
        parameters=(
            PrimitiveParameter(name="replacement", kind="replacement", description="Remplacement avec references de groupes."),
        ),
    ),
    PrimitiveDefinition(
        id="repair.none",
        family="repair",
        input_type="finding",
        output_type="patch",
        deterministic=True,
        patchable=False,
        description="Conserve le finding sans proposer de modification automatique.",
    ),
)


def primitive_catalog_for_prompt() -> dict[str, object]:
    """Return a JSON-safe catalogue containing identifiers, not runtime values."""
    return {
        "version": "1.0",
        "references": [item.model_dump(mode="json") for item in REFERENCE_CATALOG],
        "primitives": [item.model_dump(mode="json") for item in PRIMITIVE_CATALOG],
    }
