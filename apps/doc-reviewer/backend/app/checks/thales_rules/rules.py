"""Canonical THALES rule definitions built through one factory."""

from __future__ import annotations

import re
from typing import Literal

from app.checks.client_bundle import ClientRuleDefinition
from app.core.compiled_rules import (
    Check,
    CompiledRule,
    Condition,
    FieldRef,
    RuleExample,
    RulePrerequisite,
    RuleTarget,
)


_STANDARD_CODE = "THALES-CUSTOM"
_CATALOG_VERSION = "v1"
_ALL_PAGE_TARGET = RuleTarget(page="all", region="full_page")
_MODIFIED_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_state="modified",
)
_MODIFIED_FOOTER_TARGET = RuleTarget(
    page="all",
    region="footer",
    page_state="modified",
)
_TP2_TARGET = RuleTarget(page="all", region="full_page", page_type="TP2")
_HIGHLIGHTS_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_types=["HIGHLIGHTS", "HIGHLIGHTS_PAGE_1"],
)
_HIGHLIGHTS_FIRST_PAGE_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_type="HIGHLIGHTS_PAGE_1",
)
_HEADER_TARGET = RuleTarget(
    page="all",
    region="header",
    excluded_page_types=["TP1"],
)
_HIGHLIGHTS_HEADER_TARGET = RuleTarget(
    page="all",
    region="header",
    page_types=["HIGHLIGHTS", "HIGHLIGHTS_PAGE_1"],
)
_TP1_DOCUMENT_TARGET = RuleTarget(
    page="all",
    region="body",
    page_type="TP1",
)
DOCUMENT_TYPES = [
    "OVERHAUL MANUAL",
    "COMPONENT MAINTENANCE MANUAL",
    "MAINTENANCE MANUAL",
    "ABBREVIATED COMPONENT MAINTENANCE MANUAL",
    "OPERATING MANUAL",
    "ILLUSTRATED PARTS CATALOG",
    "COMPONENT MAINTENANCE PARTS LIST",
    "OPERATING MANUAL PARTS LIST",
]
_DOCUMENT_TYPE_ALTERNATION = "|".join(
    r"\s+".join(re.escape(part) for part in document_type.split())
    for document_type in sorted(DOCUMENT_TYPES, key=len, reverse=True)
)
DOCUMENT_TYPE_PATTERN = rf"(?i)(?<!\w)(?:{_DOCUMENT_TYPE_ALTERNATION})(?!\w)"
HIGHLIGHTS_DOCUMENT_TYPE_PATTERN = (
    rf"(?im)^\s*(?:{_DOCUMENT_TYPE_ALTERNATION})"
    r"(?:\s+with\s+Illustrated\s+Parts\s+List)?\s*$"
    r"\s*^\s*ATA\s+No\b"
)
_TP1_REVISION_TARGET = RuleTarget(page="all", region="footer", page_type="TP1")
_EXPECTED_TP1_REVISION_NUMBER_PATTERN = (
    r"(?i)(?<!\w)Revision\s+No\.?\s*{{meta_revision_number}}(?!\w)"
    r"(?=[\s\S]*\bFirst\s+Issue\b)"
)
_EXPECTED_TP1_FIRST_ISSUE_PATTERN = (
    r"(?i)(?<!\w)First\s+issue\s*:\s*{{meta_first_issue_date}}(?!\w)"
)
_EXPECTED_HIGHLIGHTS_REVISION_PATTERN = (
    r"(?i)(?<!\w)REVISION\s+No\.?\s*{{meta_revision_number}}\s+DATED\s+"
    r"{{meta_revision_date}}(?!\w)"
)
_EXPECTED_HIGHLIGHTS_ATA_PATTERN = r"(?i)(?<!\w)ATA\s+No\.?\s*{{meta_cmm_number}}(?!\w)"
_UNEXPECTED_HIGHLIGHTS_PNR_PATTERN = (
    r"(?i)(?<=PNR: )(?!{{meta_pnr_number}}(?!\w))"
    r"\d+-\d{3}-[A-Z]{2}(?!\w)"
)
_LETTER_DIGIT_CONFUSION_PATTERN = (
    r"(?<!\w)(?:"
    r"(?![A-Z0-9]+\b)(?=[A-Za-z0-9]*[a-z])"
    r"(?=(?:[A-Za-z0-9]*[A-Za-z]){3})[A-Za-z]*[0-9][A-Za-z]+[A-Za-z]*"
    r"|(?i:(?=[0-9ilo]*[0-9])[0-9ilo]*[ilo][0-9ilo]*)"
    r")(?!\w)"
)
_COPYRIGHT_PATTERN = (
    r"(?i)\u00a9\s*\d{4}\s*-\s*\d{4}\s+"
    r"THALES\s+AVS\s+FRANCE\s+SAS\.\s+"
    r"This\s+document\s+and\s+any\s+data\s+included\s+are\s+the\s+property\s+of\s+"
    r"THALES\s+AVS\s+FRANCE\s+SAS\.\s+"
    r"They\s+cannot\s+be\s+reproduced,\s+disclosed\s+or\s+used\s+"
    r"without\s+the\s+company's\s+prior\s+written\s+approval\.?"
)
IMPORTANT_NOTICE_TEXT = """IMPORTANT NOTICE
This document and any information contained herein are the sole property of THALES AVS FRANCE SAS and have been disclosed under a License Agreement. They cannot be used, reproduced or disclosed without the prior express written approval of THALES AVS FRANCE SAS.
In particular, they shall not be used in the creation, manufacture, development or derivation of any repairs, modifications, spare parts, design, or configuration changes or to obtain EASA, FAA or any other government or regulatory approval to do so.
Should THALES AVS FRANCE SAS consent be given for reproduction in whole or in part, this notice and the notice set forth on each page of this document shall appear in any such reproduction in whole or in part.
The recipient shall not use this document for any purpose other than the one stated in the relevant applicable License agreement under which it has been disclosed and it shall be returned to THALES AVS FRANCE SAS immediately upon request.
TO BE CONSIDERED VALID FOR PART 145 REQUIREMENTS, ALL MAINTENANCE DOCUMENTATION HAS TO BE IDENTIFIED ON EACH PAGE WITH A WATERMARK AUTHORIZING ITS USE BY THE END USER COMPANY. SUCH WATERMARK MIGHT BE AS FOLLOWS:
\u201cProvided to [USER_ID] for [COMPANY_NAME] only under license agreement [LICENSE_NUMBER] for year [YEAR] only.\u201d
Users are kindly requested to notify THALES AVS FRANCE SAS of any discrepancy, omission or error found in this manual.
Please send your comments to:
THALES AVS FRANCE SAS
Technical Publications Department
AGS, Campus Thales Bordeaux
75-77 Avenue Marcel Dassault
33700 Merignac
France
E-mail: techpubs.frontoffice@fr.thalesgroup.com
If you do not yet have access to our website, you can apply through the following address:
https://www.thalesgroup.com/customer-online"""
_TEMPERATURE_WITHOUT_FAHRENHEIT_PATTERN = (
    r"(?i)(?<!\w)(?:temperature\s*:\s*)?"
    r"[+-]?\d+(?:[.,]\d+)?"
    r"(?:\s+to\s+[+-]?\d+(?:[.,]\d+)?)?\s+deg\.\s*C\b"
    r"(?!\s*\(\s*[+-]?\d+(?:[.,]\d+)?"
    r"(?:\s+to\s+[+-]?\d+(?:[.,]\d+)?)?\s+deg\.\s*F\s*\))"
)
_TEMPERATURE_RANGE_UNIT_IN_MIDDLE_PATTERN = (
    r"(?i)(?P<label>\bTemperature\s*:\s*)"
    r"(?P<lower>[+-]?\d+(?:[.,]\d+)?)\s*"
    r"(?:deg\.\s*|\u00b0\s*)?C\s+to\s+"
    r"(?P<upper>[+-]?\d+(?:[.,]\d+)?)"
    r"(?![\d.,])"
    r"(?:\s*(?:deg\.\s*|\u00b0\s*)?C)?"
)
_TEMPERATURE_RANGE_MISSING_CELSIUS_PATTERN = (
    r"(?i)(?P<label>\bTemperature\s*:\s*)"
    r"(?P<lower>[+-]?\d+(?:[.,]\d+)?)\s+to\s+"
    r"(?P<upper>[+-]?\d+(?:[.,]\d+)?)"
    r"(?![\d.,])"
    r"(?!\s+deg\.\s*C\b)"
    r"(?!\s+deg\.\s*F\b)"
    r"(?!\s*\u00b0\s*C\b)"
    r"(?:\s*C)?"
)
_NOTE_INTRODUCTION_TEXT = {
    "REPAIR": (
        "During repair operations, make sure that the environmental conditions "
        "are as follows:"
    ),
    "TESTING": (
        "During testing operations, make sure that the environmental conditions "
        "are as follows:"
    ),
    "STORAGE": (
        "During storage operations, make sure that the environmental conditions "
        "are as follows:"
    ),
}
_REPAIR_RELATIVE_HUMIDITY = (
    "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00, "
    "F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
)
_STORAGE_TEMPERATURE = (
    "Temperature: Refer to Standard Practices Manual ATA No. 20-02-00, "
    "F9111CMON-A-20-02-00-00A-812A-A – Storage and Transportation of Assemblies."
)
_THALES_TP1_ADDRESS_ELEMENTS: tuple[tuple[str, str], ...] = (
    (r"\(F9111\)", "(F9111)"),
    (r"75-77\s+Avenue\s+Marcel\s+Dassault", "75-77 Avenue Marcel Dassault"),
    (r"33700\s+M\u00e9rignac\s+-\s+France", "33700 Mérignac - France"),
    (r"Tel\s*:\s*\+33\s+\(0\)5\s+24\s+44\s+77\s+40", "Tel : +33 (0)5 24 44 77 40"),
    (r"www\.thalesgroup\.com", "www.thalesgroup.com"),
)
_REPAIR_RELATIVE_HUMIDITY_PATTERN = (
    "(?i:"
    + re.escape(_REPAIR_RELATIVE_HUMIDITY)
    .replace(r"\ ", r"\s+")
    .replace("procedure", r"proc(?:e|\u00e9|\uFFFD)dure")
    + ")"
)
_STORAGE_TEMPERATURE_PATTERN = (
    "(?i:"
    + re.escape(_STORAGE_TEMPERATURE)
    .replace(r"\ ", r"\s+")
    .replace("–", r"[-\u2010-\u2015\u2212\uFFFD]")
    + ")"
)
_NOTE_PRESSURE_PATTERN = r"\bPressure\s*:"


def _required_note_check(
    content_pattern: str,
    *,
    display: str,
    page_type: str,
    anchor: str | None = None,
    anchor_position: Literal["above", "below", "same"] = "above",
) -> Check:
    introduction_pattern = re.escape(_NOTE_INTRODUCTION_TEXT[page_type]).replace(
        r"\ ", r"\s+"
    )
    expected = (
        rf"(?i:\bNOTE\b)\s*:\s*{introduction_pattern}"
        r"(?is:(?:(?!\bNOTE\b).)*?)"
        + content_pattern
    )
    return Check(
        field="text",
        operator="regex_exists",
        expected=expected,
        require_all=True,
        expected_display=display,
        suggestion_mode="fuzzy",
        missing_anchor=anchor,
        missing_anchor_position=anchor_position,
    )


def rule(
    *,
    code: str,
    name: str,
    description: str,
    message: str,
    kind: str,
    severity: Literal["info", "warning", "error"],
    presentation_severity: Literal["info", "warning", "error"] | None = None,
    target: RuleTarget,
    checks: list[Check],
    failure_message: str | None = None,
    only_if: Condition | None = None,
    valid_examples: list[RuleExample] | None = None,
    invalid_examples: list[RuleExample] | None = None,
    prerequisites: list[RulePrerequisite] | None = None,
    translations: dict[str, dict[str, str]] | None = None,
) -> ClientRuleDefinition:
    compiled_rule = CompiledRule(
        id=code,
        topic=name,
        failure_message=failure_message,
        severity=severity,
        execution="deterministic",
        target=target,
        checks=checks,
        source="standard_rule",
        origin_ref=f"{_STANDARD_CODE}:{_CATALOG_VERSION}:{code}",
        only_if=only_if,
        valid_examples=valid_examples or [],
        invalid_examples=invalid_examples or [],
        prerequisites=prerequisites or [],
    )
    return ClientRuleDefinition(
        compiled_rule=compiled_rule,
        name=name,
        description=description,
        message=message,
        kind=kind,
        presentation_severity=presentation_severity,
        translations=translations or {},
    )


CUSTOM_THALES_LOGO_FONT_SIZE = rule(
    code="CUSTOM_THALES_LOGO_FONT_SIZE",
    name="Taille du logo THALES sur les pages hors TP1",
    description=(
        "Le T de la police Thales en debut de page doit avoir une taille "
        "de 31 pt hors pages TP1."
    ),
    message="La taille du logo THALES hors TP1 n'est pas 31 pt.",
    kind="field_required",
    severity="warning",
    target=RuleTarget(
        page="all",
        region="full_page",
        excluded_page_types=["TP1"],
    ),
    checks=[
        Check(
            field="thales_logo_t",
            operator="font_size_equals",
            expected=31,
            require_all=True,
        ),
    ],
    failure_message="taille du logo THALES non conforme hors TP1.",
    translations={
        "en": {
            "description": "The Thales T at the start of the page must use a 31 pt font outside TP1 pages.",
            "message": "The THALES logo size outside TP1 is not 31 pt.",
        }
    },
)

CUSTOM_CMM_NUMBER_FONT_SIZE = rule(
    code="CUSTOM_CMM_NUMBER_FONT_SIZE",
    name="Taille de police du numero CMM (ATA)",
    description=(
        "Le numero CMM (ATA) present dans le footer doit utiliser une taille "
        "de police de 23 pt."
    ),
    message="La taille de police du numero CMM (ATA) n'est pas 23 pt.",
    kind="field_required",
    severity="warning",
    presentation_severity="error",
    target=RuleTarget(page="all", region="footer"),
    checks=[
        Check(
            field="cmm_number",
            operator="font_size_equals",
            expected=23,
            require_all=True,
        ),
    ],
    failure_message="taille de police du numero CMM non conforme.",
    only_if=Condition(field="meta_cmm_number", state="present"),
    translations={
        "en": {
            "description": "The CMM number (ATA) in the footer must use a 23 pt font.",
            "message": "The CMM number (ATA) font size is not 23 pt.",
        }
    },
)

CUSTOM_CMM_NUMBER = rule(
    code="CUSTOM_CMM_NUMBER",
    name="Numero CMM conforme au contexte du document",
    description=(
        "Le numero ATA/CMM present dans le pied de page doit correspondre a "
        "meta_cmm_number dans le contexte du document. Ce controle verifie la "
        "valeur; la taille de 23 pt est controlee par une regle distincte."
    ),
    message="Le numero CMM ne correspond pas au contexte du document.",
    kind="field_required",
    severity="error",
    target=RuleTarget(page="all", region="footer"),
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=r"(?<!\w){{meta_cmm_number}}(?!\w)",
            require_all=True,
            expected_display="{{meta_cmm_number}}",
            missing_anchor=r"(?i)\bFirst\s+Issue\b",
        ),
    ],
    failure_message="Numero CMM non conforme",
    translations={
        "en": {
            "description": (
                "The ATA/CMM number in the footer must match meta_cmm_number in "
                "the document context. This check validates the value; a separate "
                "rule checks the 23 pt font size."
            ),
            "message": "The CMM number does not match the document context.",
        }
    },
)

CUSTOM_TP1_REVISION_NUMBER = rule(
    code="CUSTOM_TP1_REVISION_NUMBER",
    name="Numero de revision du footer TP1 conforme au mapping",
    description=(
        "Chaque page TP1 doit contenir dans son footer 'Revision No. 0X' "
        "au-dessus de 'First Issue', avec 0X egal au numero de revision "
        "saisi dans le mapping (sans le prefixe 'Rev.'). La checklist demande "
        "aussi que ce numero soit celui de la revision precedente + 1; cette "
        "progression n'est pas calculee par cette regle."
    ),
    message=(
        "Le numero de revision du footer TP1 est absent ou ne correspond "
        "pas au mapping."
    ),
    kind="field_required",
    severity="error",
    target=_TP1_REVISION_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=_EXPECTED_TP1_REVISION_NUMBER_PATTERN,
            require_all=True,
            expected_display="Revision No. {{meta_revision_number}}",
            missing_anchor=r"(?i)\bFirst\s+Issue\b",
        ),
    ],
    failure_message="numéro de revision non conforme.",
    translations={
        "en": {
            "description": (
                "Each TP1 page must contain 'Revision No. 0X' above 'First Issue' "
                "in its footer, with 0X equal to the revision number in the mapping. "
                "The checklist also requires the previous revision number plus 1; "
                "this rule does not calculate that progression."
            ),
            "message": "The TP1 footer revision number is missing or does not match the mapping.",
        }
    },
)

CUSTOM_TP1_FIRST_ISSUE_DATE = rule(
    code="CUSTOM_TP1_FIRST_ISSUE_DATE",
    name="Date de premiere issue du footer TP1 conforme au mapping",
    description=(
        "Chaque page TP1 doit contenir dans son footer 'First Issue: date' "
        "avec une date egale a la date de premiere issue saisie dans le mapping."
    ),
    message=(
        "La date de premiere issue du footer TP1 est absente ou ne correspond "
        "pas au mapping."
    ),
    kind="field_required",
    severity="warning",
    target=_TP1_REVISION_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=_EXPECTED_TP1_FIRST_ISSUE_PATTERN,
            require_all=True,
            expected_display="First issue: {{meta_first_issue_date}}",
            missing_anchor=r"(?i)\bFirst\s+issue\s*:",
            missing_anchor_position="same",
        ),
    ],
    failure_message="date de premiere issue non conforme.",
    translations={
        "en": {
            "description": (
                "Each TP1 page must contain 'First Issue: date' in its footer, "
                "with a date equal to the first issue date in the mapping."
            ),
            "message": "The TP1 footer first issue date is missing or does not match the mapping.",
        }
    },
)

CUSTOM_HIGHLIGHTS_REVISION_HEADER = rule(
    code="CUSTOM_HIGHLIGHTS_REVISION_HEADER",
    name="En-tete de revision present au-dessus du tableau Highlights",
    description=(
        "La page dont le nom contient Highlights doit afficher au-dessus du "
        "tableau l'en-tete REVISION No. avec le numero et la date du mapping."
    ),
    message=(
        "L'en-tete de revision Highlights est absent, incorrect ou place "
        "apres le tableau."
    ),
    kind="field_required",
    severity="warning",
    target=_HIGHLIGHTS_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=_EXPECTED_HIGHLIGHTS_REVISION_PATTERN,
            require_all=True,
            expected_display="REVISION No. {{meta_revision_number}} DATED {{meta_revision_date}}",
            suggestion_mode="single",
            missing_anchor=r"(?i)\bHighlights\b",
            missing_anchor_position="above",
        ),
    ],
    failure_message="En-tete de revision Highlights non conforme.",
    translations={
        "en": {
            "description": (
                "The page whose name contains Highlights must show the REVISION "
                "No. header with the mapped number and date above the table."
            ),
            "message": "The Highlights revision header is missing, incorrect, or placed after the table.",
        }
    },
)

CUSTOM_HIGHLIGHTS_DELETION_DESCRIPTION = rule(
    code="CUSTOM_HIGHLIGHTS_DELETION_DESCRIPTION",
    name="Description obligatoire pour les suppressions des Highlights",
    description=(
        "Toute ligne D des Highlights doit porter en face la mention "
        "Chapter deleted ou Page deleted."
    ),
    message="La suppression des Highlights ne porte pas la mention attendue.",
    kind="field_required",
    severity="error",
    target=_HIGHLIGHTS_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "highlights_deleted_description"},
        )
    ],
    failure_message="Description de suppression absente ou incorrecte dans les Highlights.",
    translations={
        "en": {
            "description": (
                "Every D row in Highlights must have 'Chapter deleted' or "
                "'Page deleted' in its description."
            ),
            "message": "The Highlights deletion row is missing the required description.",
        }
    },
)

CUSTOM_HIGHLIGHTS_REVISED_DESCRIPTION = rule(
    code="CUSTOM_HIGHLIGHTS_REVISED_DESCRIPTION",
    name="Description obligatoire pour les lignes R des Highlights",
    description=(
        "Toute ligne R des Highlights doit avoir une description en face. "
        "Pour l'Illustrated Parts List, la description peut figurer en face "
        "de sa rubrique et s'appliquer aux lignes R suivantes."
    ),
    message="Une ligne R des Highlights ne porte pas de description.",
    kind="field_required",
    severity="error",
    target=_HIGHLIGHTS_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "highlights_revised_description"},
        )
    ],
    failure_message="Description de modification absente dans les Highlights.",
    translations={
        "en": {
            "description": (
                "Every R row in Highlights must have a description, except that "
                "Illustrated Parts List may use the description on its section row."
            ),
            "message": "A revised Highlights row is missing its description.",
        }
    },
)

CUSTOM_CHAPTER_NUMBER_SEQUENCE = rule(
    code="CUSTOM_CHAPTER_NUMBER_SEQUENCE",
    name="Ordre des chapitres numerotes",
    description=(
        "Dans chaque serie de pages de chapitre, les titres numerotes "
        "1., 2., 3., etc. doivent se suivre sans omission ni inversion."
    ),
    message="L'ordre de numerotation des chapitres est incoherent.",
    kind="field_required",
    severity="warning",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "chapter_sequence"},
        )
    ],
    failure_message="Ordre des chapitres numerotes incoherent.",
    translations={
        "en": {
            "description": (
                "Within each chapter page series, numbered headings such as "
                "1., 2., 3., etc. must follow in order without gaps or reversals."
            ),
            "message": "The numbered chapter headings are out of order.",
        }
    },
)

CUSTOM_LIST_OF_MATERIALS_CODE_NO_PARENTHESES = rule(
    code="CUSTOM_LIST_OF_MATERIALS_CODE_NO_PARENTHESES",
    name="Code sans parentheses dans la LIST OF MATERIALS",
    description=(
        "La colonne CODE du tableau LIST OF MATERIALS ne doit contenir "
        "aucune parenthese. Les parentheses dans les autres colonnes ne sont pas controlees."
    ),
    message="Un code de la LIST OF MATERIALS contient des parentheses.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "list_materials_code_parentheses"},
        )
    ],
    failure_message="La colonne CODE de la LIST OF MATERIALS ne doit pas contenir de parentheses.",
    translations={
        "en": {
            "description": (
                "The CODE column in the LIST OF MATERIALS table must not contain "
                "parentheses. Parentheses in other columns are not checked."
            ),
            "message": "A LIST OF MATERIALS code contains parentheses.",
        }
    },
)

CUSTOM_LIST_OF_MATERIALS_CODE_LOWERCASE = rule(
    code="CUSTOM_LIST_OF_MATERIALS_CODE_LOWERCASE",
    name="Codes de la LIST OF MATERIALS en minuscules",
    description=(
        "Aucune lettre majuscule n'est autorisee dans la colonne CODE du tableau "
        "LIST OF MATERIALS."
    ),
    message="Les codes de la LIST OF MATERIALS doivent etre en minuscules.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "list_materials_code_lowercase"},
        )
    ],
    failure_message="La colonne CODE de la LIST OF MATERIALS doit etre en minuscules.",
    translations={
        "en": {
            "description": (
                "Uppercase letters are not allowed in the CODE column of the "
                "LIST OF MATERIALS table."
            ),
            "message": "LIST OF MATERIALS codes must use lowercase letters.",
        }
    },
)

CUSTOM_LIST_OF_MATERIALS_SUPPLIER_FSCM = rule(
    code="CUSTOM_LIST_OF_MATERIALS_SUPPLIER_FSCM",
    name="Numero FSCM obligatoire dans la colonne fournisseur",
    description=(
        "Dans la colonne SUPPLIERS TRADE NAME AND CODE FSCM de la LIST OF "
        "MATERIALS, chaque nom de fournisseur doit etre suivi d'un numero FSCM "
        "a cinq caracteres entre parentheses : (FSCM XXXXX)."
    ),
    message="Un fournisseur de la LIST OF MATERIALS n'a pas de numero FSCM valide.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "list_materials_supplier_fscm"},
        )
    ],
    failure_message=(
        "Chaque nom de fournisseur doit etre suivi d'un numero au format (FSCM XXXXX)."
    ),
    translations={
        "en": {
            "description": (
                "In the SUPPLIERS TRADE NAME AND CODE FSCM column of the LIST OF "
                "MATERIALS, each supplier name must be followed by a five-character "
                "FSCM number in parentheses: (FSCM XXXXX)."
            ),
            "message": "A LIST OF MATERIALS supplier is missing a valid FSCM number.",
        }
    },
)

CUSTOM_REVISION_BAR_NEW_PAGE = rule(
    code="CUSTOM_REVISION_BAR_NEW_PAGE",
    name="Barre de revision pleine hauteur sur les pages nouvelles",
    description=(
        "Chaque page declaree N dans les Highlights doit porter une barre de "
        "revision noire presque pleine hauteur, du haut du contenu jusqu'au "
        "pied de page."
    ),
    message="Une page nouvelle ne comporte pas de barre de revision pleine hauteur.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "revision_bar_new"},
        )
    ],
    failure_message=(
        "Chaque page N doit porter une barre de revision noire du logo au pied de page."
    ),
    translations={
        "en": {
            "description": (
                "Every page declared N in Highlights must have a nearly full-height "
                "black revision bar from the top of the content to the footer."
            ),
            "message": "A new page is missing its full-height revision bar.",
        }
    },
)

CUSTOM_REVISION_BAR_MODIFIED_PAGE = rule(
    code="CUSTOM_REVISION_BAR_MODIFIED_PAGE",
    name="Barre de revision presente sur les pages modifiees",
    description=(
        "Chaque page declaree R dans les Highlights doit porter au moins une "
        "barre de revision noire."
    ),
    message="Une page modifiee ne comporte pas de barre de revision.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "revision_bar_modified"},
        )
    ],
    failure_message="Chaque page R doit comporter au moins une barre de revision noire.",
    translations={
        "en": {
            "description": (
                "Every page declared R in Highlights must have at least one black "
                "revision bar."
            ),
            "message": "A modified page is missing a revision bar.",
        }
    },
)

CUSTOM_REVISION_BAR_MARGIN_POSITION = rule(
    code="CUSTOM_REVISION_BAR_MARGIN_POSITION",
    name="Position de la barre de revision par rapport a la marge",
    description=(
        "Sur les pages N et R portant une barre, son ecart horizontal par rapport "
        "a la marge gauche doit etre l=-0,38 cm (tolerance +/- 0,10 cm)."
    ),
    message="Une barre de revision est mal positionnee par rapport a la marge.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "revision_bar_margin"},
        )
    ],
    failure_message="La barre de revision doit etre a l=-0,38 cm de la marge gauche.",
    translations={
        "en": {
            "description": (
                "On N and R pages with a revision bar, its horizontal offset from "
                "the left margin must be l=-0.38 cm (tolerance +/- 0.10 cm)."
            ),
            "message": "A revision bar is incorrectly positioned relative to the margin.",
        }
    },
)

CUSTOM_TP1_REVISION_BAR_FOOTER = rule(
    code="CUSTOM_TP1_REVISION_BAR_FOOTER",
    name="Barre de revision sur tout le footer de la TP1",
    description=(
        "Sur la page TP 1 declaree R, une barre de revision noire doit longer le "
        "footer depuis la ligne Revision, en couvrant First Issue, jusqu'en dessous "
        "de la derniere ligne du copyright."
    ),
    message="La TP1/R n'a pas de barre de revision sur toute la hauteur du footer.",
    kind="field_required",
    severity="error",
    target=_TP1_REVISION_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "revision_bar_tp1_footer"},
        )
    ],
    failure_message=(
        "La barre TP1/R doit partir de Revision, couvrir First Issue et descendre "
        "sous le copyright."
    ),
    translations={
        "en": {
            "description": (
                "On TP 1 declared R, a black revision bar must run through the "
                "footer from Revision, covering First Issue, to below the final "
                "copyright line."
            ),
            "message": "The TP1/R revision bar does not span the full footer.",
        }
    },
)

CUSTOM_TP2_REVISION_BAR_BODY_ONLY = rule(
    code="CUSTOM_TP2_REVISION_BAR_BODY_ONLY",
    name="Barre TP2/R limitee au texte du corps",
    description=(
        "Sur une page TP2 declaree R, la barre de revision doit se trouver en "
        "regard du texte du corps, sans traverser l'en-tete ni le pied de page."
    ),
    message="La barre de revision d'une page TP2/R est dans l'en-tete ou le pied de page.",
    kind="field_required",
    severity="error",
    target=_TP2_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "revision_bar_tp2_body"},
        )
    ],
    failure_message=(
        "Sur TP2/R, la barre ne doit apparaitre qu'en regard du texte modifie."
    ),
    translations={
        "en": {
            "description": (
                "On a TP2 page declared R, the revision bar must align with body "
                "text and must not run through the header or footer."
            ),
            "message": "A TP2/R revision bar appears in the header or footer.",
        }
    },
)

CUSTOM_VENDOR_CODE_LIST_REFERENCE = rule(
    code="CUSTOM_VENDOR_CODE_LIST_REFERENCE",
    name="Code fournisseur et adresse THALES",
    description=(
        "Seule l'entree THALES est verifiee dans les tableaux de codes fournisseurs: "
        "le code VF9111 doit correspondre a l'adresse officielle THALES AVS FRANCE "
        "SAS, 75-77 AV MARCEL DASSAULT, CAMPUS THALES BORDEAUX, 33700 MERIGNAC, "
        "FRANCE. Les autres fournisseurs ne sont pas controles."
    ),
    message="Le code fournisseur ou l'adresse THALES ne correspond pas aux valeurs attendues.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="vendor_code_list",
            operation_params={"control": "reference"},
        )
    ],
    failure_message=(
        "L'entree THALES ne correspond pas au code et a l'adresse attendus."
    ),
    translations={
        "en": {
            "description": (
                "Only the THALES entry in vendor code tables is validated: code "
                "VF9111 must match the official THALES AVS FRANCE SAS address at "
                "75-77 AV MARCEL DASSAULT, CAMPUS THALES BORDEAUX, 33700 MERIGNAC, "
                "FRANCE. Other vendors are ignored."
            ),
            "message": "The THALES vendor code or address does not match the expected values.",
        }
    },
)

CUSTOM_NI_PART_NUMBER_ORDER = rule(
    code="CUSTOM_NI_PART_NUMBER_ORDER",
    name="Numerical Index trie par Part Number croissant",
    description=(
        "Dans le Numerical Index, les Part Numbers de la colonne Part Number "
        "doivent etre en ordre alphanumerique lexicographique, sans tenir compte "
        "de la casse, y compris entre les pages consecutives. Les references qui "
        "commencent par une lettre precedent celles qui commencent par un chiffre."
    ),
    message="Les Part Numbers du Numerical Index ne sont pas en ordre croissant.",
    kind="field_required",
    severity="warning",
    target=RuleTarget(
        page="all",
        region="full_page",
        page_type="NUMERICAL_INDEX",
    ),
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "ni_part_number_order"},
        )
    ],
    failure_message="La colonne Part Number du Numerical Index doit etre en ordre croissant.",
    translations={
        "en": {
            "description": (
                "Alphanumeric values in the Numerical Index Part Number column must "
                "be in case-insensitive lexicographic order, including across "
                "consecutive pages. Letter-prefixed values precede digit-prefixed values."
            ),
            "message": "The Numerical Index Part Numbers are not in ascending order.",
        }
    },
)

CUSTOM_HIGHLIGHTS_ATA_NUMBER = rule(
    code="CUSTOM_HIGHLIGHTS_ATA_NUMBER",
    name="Numero ATA present sur la premiere page Highlights",
    description=(
        "La premiere page Highlights doit contenir le numero ATA correspondant "
        "au numero CMM du mapping du document."
    ),
    message="Le numero ATA de la premiere page Highlights est absent ou incorrect.",
    kind="field_required",
    severity="error",
    target=_HIGHLIGHTS_FIRST_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=_EXPECTED_HIGHLIGHTS_ATA_PATTERN,
            require_all=True,
            expected_display="ATA No {{meta_cmm_number}}",
            suggestion_mode="single",
            missing_anchor=r"(?i)\bATA\s+No\b",
            missing_anchor_position="same",
        ),
    ],
    failure_message="numero ATA Highlights absent ou non conforme.",
    only_if=Condition(field="meta_cmm_number", state="present"),
    translations={
        "en": {
            "description": (
                "The first Highlights page must contain the ATA number matching "
                "the document CMM number in the mapping."
            ),
            "message": "The ATA number on the first Highlights page is missing or incorrect.",
        }
    },
)

CUSTOM_HIGHLIGHTS_PNR_HEADER = rule(
    code="CUSTOM_HIGHLIGHTS_PNR_HEADER",
    name="Numeros PNR presents et conformes dans l'en-tete Highlights",
    description=(
        "L'en-tete de chaque page Highlights doit contenir tous les numeros "
        "PNR renseignes dans le mapping du document."
    ),
    message="Un ou plusieurs numeros PNR de l'en-tete Highlights sont absents ou incorrects.",
    kind="field_required",
    severity="error",
    target=_HIGHLIGHTS_HEADER_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={"control": "highlights_pnr_header"},
        ),
    ],
    failure_message="Numeros PNR de l'en-tete Highlights manquants ou non conformes.",
    only_if=Condition(field="meta_pnr_number", state="present"),
    translations={
        "en": {
            "description": "The header of every Highlights page must contain all PNR numbers in the document mapping.",
            "message": "One or more Highlights header PNR numbers are missing or incorrect.",
        }
    },
)

CUSTOM_HEADER_DOCUMENT_TYPE = rule(
    code="CUSTOM_HEADER_DOCUMENT_TYPE",
    name="Type de document present dans les en-tetes hors TP1",
    description=(
        "Chaque en-tete hors TP1 doit contenir l'un des types de document "
        "autorises : OVERHAUL MANUAL, MAINTENANCE MANUAL, COMPONENT "
        "MAINTENANCE MANUAL, ABBREVIATED COMPONENT MAINTENANCE MANUAL, "
        "OPERATING MANUAL, ILLUSTRATED PARTS CATALOG, COMPONENT MAINTENANCE "
        "PARTS LIST ou OPERATING MANUAL PARTS LIST."
    ),
    message="Le type de document est absent de l'en-tete.",
    kind="field_required",
    severity="error",
    target=_HEADER_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=DOCUMENT_TYPE_PATTERN,
            require_all=True,
        ),
    ],
    failure_message="type de document absent de l'en-tete.",
    translations={
        "en": {
            "description": (
                "Every non-TP1 header must contain an allowed document type: "
                "OVERHAUL MANUAL, MAINTENANCE MANUAL, COMPONENT MAINTENANCE "
                "MANUAL, ABBREVIATED COMPONENT MAINTENANCE MANUAL, OPERATING "
                "MANUAL, ILLUSTRATED PARTS CATALOG, COMPONENT MAINTENANCE "
                "PARTS LIST, or OPERATING MANUAL PARTS LIST."
            ),
            "message": "The document type is missing from the header.",
        }
    },
)

CUSTOM_TP1_HEADER_DOCUMENT_TYPE = rule(
    code="CUSTOM_TP1_HEADER_DOCUMENT_TYPE",
    name="Type de document present dans le contenu TP1",
    description=(
        "Chaque contenu TP1 doit contenir l'un des types de document autorises : "
        "OVERHAUL MANUAL, MAINTENANCE MANUAL, COMPONENT MAINTENANCE MANUAL, "
        "ABBREVIATED COMPONENT MAINTENANCE MANUAL, OPERATING MANUAL, "
        "ILLUSTRATED PARTS CATALOG, COMPONENT MAINTENANCE PARTS LIST ou "
        "OPERATING MANUAL PARTS LIST."
    ),
    message="Le type de document est absent du contenu TP1.",
    kind="field_required",
    severity="error",
    target=_TP1_DOCUMENT_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=DOCUMENT_TYPE_PATTERN,
            require_all=True,
        ),
    ],
    failure_message="type de document absent du contenu TP1.",
    translations={
        "en": {
            "description": (
                "Every TP1 page content must contain an allowed document type: "
                "OVERHAUL MANUAL, MAINTENANCE MANUAL, COMPONENT MAINTENANCE "
                "MANUAL, ABBREVIATED COMPONENT MAINTENANCE MANUAL, OPERATING "
                "MANUAL, ILLUSTRATED PARTS CATALOG, COMPONENT MAINTENANCE "
                "PARTS LIST, or OPERATING MANUAL PARTS LIST."
            ),
            "message": "The document type is missing from the TP1 page content.",
        }
    },
)

CUSTOM_PNR_PAGE_VALUE = rule(
    code="CUSTOM_PNR_PAGE_VALUE",
    name="Numero PNR present dans la page conforme au mapping",
    description=(
        "Le numero apres 'PNR:' sur la page Highlights doit correspondre au "
        "mapping du document."
    ),
    message="Le numero PNR de la page Highlights ne correspond pas au mapping.",
    kind="regex_flag",
    severity="error",
    target=_HIGHLIGHTS_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex",
            expected=_UNEXPECTED_HIGHLIGHTS_PNR_PATTERN,
            replacement="{{meta_pnr_number}}",
        ),
    ],
    failure_message="Numero PNR present dans la page non conforme.",
    only_if=Condition(field="meta_pnr_number", state="present"),
    translations={
        "en": {
            "description": "The number after 'PNR:' on a Highlights page must match the document mapping.",
            "message": "The Highlights page PNR number does not match the mapping.",
        }
    },
)

CUSTOM_TP1_PNR_PAGE_VALUE = rule(
    code="CUSTOM_TP1_PNR_PAGE_VALUE",
    name="Numero PNR present dans la page TP1 conforme au mapping",
    description=(
        "Toute valeur PNR presente dans le corps d'une page TP1 doit correspondre "
        "a l'une des valeurs du mapping du document."
    ),
    message="Le numero PNR de la page TP1 ne correspond pas au mapping.",
    kind="regex_flag",
    severity="error",
    target=_TP1_DOCUMENT_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="document_structure",
            operation_params={
                "control": "tp1_pnr_page_value",
                "suppress_fallback_suggestion": True,
            },
        ),
    ],
    failure_message="Numero PNR present dans la page TP1 non conforme.",
    only_if=Condition(field="meta_pnr_number", state="present"),
    translations={
        "en": {
            "description": (
                "Every PNR value in the body of a TP1 page must match one of the "
                "document mapping values."
            ),
            "message": "The TP1 page PNR number does not match the mapping.",
        }
    },
)

CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE = rule(
    code="CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE",
    name="Type de document present au-dessus du numero ATA des Highlights",
    description=(
        "La premiere page Highlights doit afficher un type de document autorise "
        "au-dessus du numero ATA : OVERHAUL MANUAL, MAINTENANCE MANUAL, "
        "COMPONENT MAINTENANCE MANUAL, ABBREVIATED COMPONENT MAINTENANCE "
        "MANUAL, OPERATING MANUAL, ILLUSTRATED PARTS CATALOG, COMPONENT "
        "MAINTENANCE PARTS LIST ou OPERATING MANUAL PARTS LIST."
    ),
    message="Le type de document est absent au-dessus du numero ATA Highlights.",
    kind="field_required",
    severity="error",
    target=_HIGHLIGHTS_FIRST_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="highlights_document_type",
            missing_anchor=r"(?i)\bATA\s+No\b",
            missing_anchor_position="above",
        ),
    ],
    failure_message="type de document absent au-dessus du numero ATA Highlights.",
    translations={
        "en": {
            "description": (
                "The first Highlights page must show an allowed document type above "
                "the ATA number: OVERHAUL MANUAL, MAINTENANCE MANUAL, COMPONENT "
                "MAINTENANCE MANUAL, ABBREVIATED COMPONENT MAINTENANCE MANUAL, "
                "OPERATING MANUAL, ILLUSTRATED PARTS CATALOG, COMPONENT "
                "MAINTENANCE PARTS LIST, or OPERATING MANUAL PARTS LIST."
            ),
            "message": "The document type is missing above the Highlights ATA number.",
        }
    },
)

CUSTOM_HIGHLIGHTS_LEGEND_FOOTER = rule(
    code="CUSTOM_HIGHLIGHTS_LEGEND_FOOTER",
    name="Legende du tableau Highlights avant le pied de page",
    description=(
        "Sur chaque page Highlights, le tableau et sa legende "
        "(N: New - D: Deleted ...) doivent se terminer juste avant le pied "
        "de page, sans ligne de texte entre les deux."
    ),
    message=(
        "Une ligne de texte s'intercale entre la legende du tableau Highlights "
        "et le pied de page."
    ),
    kind="field_required",
    severity="warning",
    target=_HIGHLIGHTS_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="highlights_legend_footer",
        ),
    ],
    failure_message=(
        "Le tableau et la legende Highlights doivent se terminer juste avant "
        "le pied de page, sans ligne de texte intercalaire."
    ),
    translations={
        "en": {
            "description": (
                "On every Highlights page, the table and its legend "
                "(N: New - D: Deleted ...) must end immediately before the "
                "footer, with no intervening text line."
            ),
            "message": (
                "A text line appears between the Highlights table legend "
                "and the footer."
            ),
        }
    },
)


CUSTOM_INTRODUCTION_SHOP_VERIFICATION = rule(
    code="CUSTOM_INTRODUCTION_SHOP_VERIFICATION",
    name="Shop Verification conforme au constructeur du mapping",
    description=(
        "La page INTRODUCTION doit contenir le bloc Shop Verification attendu "
        "pour le constructeur choisi dans le mapping (Airbus ou Boeing)."
    ),
    message="Le bloc Shop Verification de l'INTRODUCTION est absent ou incorrect.",
    kind="field_required",
    severity="error",
    target=RuleTarget(
        page="all",
        region="full_page",
        page_type="INTRODUCTION",
    ),
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="shop_verification",
            require_all=True,
        ),
    ],
    failure_message="Shop Verification INTRODUCTION non conforme.",
    only_if=Condition(field="meta_manufacturer", state="present"),
    translations={
        "en": {
            "description": (
                "The INTRODUCTION page must contain the expected Shop Verification "
                "block for the manufacturer selected in the mapping."
            ),
            "message": "The INTRODUCTION Shop Verification block is missing or incorrect.",
        }
    },
)

CUSTOM_HIGHLIGHTS_HOLDER = rule(
    code="CUSTOM_HIGHLIGHTS_HOLDER",
    name="Destinataire des Highlights conforme au titre TP1",
    description=(
        "La premiere page Highlights doit commencer par la phrase « TO: HOLDER "
        "OF <titre> », avec <titre> egal au titre en gras de la page TP1."
    ),
    message="La phrase TO: HOLDER OF des Highlights ne correspond pas au titre TP1.",
    kind="field_required",
    severity="error",
    target=_HIGHLIGHTS_FIRST_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="highlights_holder",
        ),
    ],
    failure_message=(
        "La phrase TO: HOLDER OF des Highlights ne correspond pas au titre TP1."
    ),
    translations={
        "en": {
            "description": (
                "The first Highlights page must start with 'TO: HOLDER OF <title>', "
                "where <title> matches the bold title on the TP1 page."
            ),
            "message": "The Highlights TO: HOLDER OF sentence does not match the TP1 title.",
        }
    },
)

CUSTOM_FOOTER_PAGE_NUMBER = rule(
    code="CUSTOM_FOOTER_PAGE_NUMBER",
    name="Numero de page present et conforme dans le pied de page",
    description=(
        "Chaque page doit afficher un seul numero dans le pied de page, sans "
        "forme combinee telle que Page 25/26. Les pages "
        "LEP, ROR, Highlights et Title Page sont verifiees contre leur prefixe "
        "et leur ordre attendu (LEP Page 1, ROR Page 1, TP 1, etc.)."
    ),
    message="Le numero de page du pied de page est absent ou incorrect.",
    kind="field_required",
    severity="error",
    target=RuleTarget(page="all", region="full_page"),
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "footer_page_number"},
        ),
    ],
    failure_message="numero de page absent, multiple ou incoherent dans le pied de page.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "Every page must show one page number in the footer, not a combined "
                "label such as Page 25/26. LEP, ROR, Highlights, "
                "and Title Page pages are checked against their expected prefix and order."
            ),
            "message": "The footer page number is missing or incorrect.",
        }
    },
)

CUSTOM_SENTENCE_PUNCTUATION = rule(
    code="CUSTOM_SENTENCE_PUNCTUATION",
    name="Ponctuation obligatoire absente des phrases et enumerations",
    description=(
        "Sur les pages modifiees, chaque phrase doit se terminer par un point et "
        "chaque enumeration doit suivre le signe terminal majoritaire (point, "
        "point-virgule, virgule ou absence de signe). En cas d'egalite, les "
        "elements intermediaires prennent une virgule et le dernier un point."
    ),
    message="Une ponctuation obligatoire est absente.",
    kind="field_required",
    severity="error",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="sentence_punctuation",
            expected="missing_required_punctuation",
        ),
    ],
    failure_message="ponctuation terminale obligatoire absente.",
    translations={
        "en": {
            "description": (
                "On modified pages, every sentence must end with a full stop and "
                "every enumeration must follow its most common terminal mark "
                "(full stop, semicolon, comma, or no mark). Ties use commas for "
                "intermediate items and a full stop for the last."
            ),
            "message": "A required punctuation mark is missing.",
        }
    },
)

CUSTOM_ENUMERATION_PUNCTUATION_SWAP = rule(
    code="CUSTOM_ENUMERATION_PUNCTUATION_SWAP",
    name="Virgule et point intervertis dans les enumerations",
    description=(
        "Sur les pages modifiees, signale a titre informatif un point a la place "
        "d'une virgule dans un element intermediaire, ou une virgule a la place "
        "du point final d'une enumeration."
    ),
    message="Un point et une virgule semblent intervertis dans cette enumeration.",
    kind="field_required",
    severity="info",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="sentence_punctuation",
            expected="enumeration_punctuation_swap",
        ),
    ],
    failure_message="virgule et point intervertis dans une enumeration.",
    translations={
        "en": {
            "description": (
                "On modified pages, informationally flags a full stop instead of "
                "a comma on an intermediate enumeration item, or a comma instead "
                "of the final full stop."
            ),
            "message": "A full stop and comma appear to be swapped in this enumeration.",
        }
    },
)

CUSTOM_PARAGRAPH_JUSTIFICATION = rule(
    code="CUSTOM_PARAGRAPH_JUSTIFICATION",
    name="Paragraphes du contenu justifies sur les pages modifiees",
    description=(
        "Sur les pages modifiees, les paragraphes de contenu multilignes doivent "
        "etre visuellement alignes a gauche et a droite, hors derniere ligne. "
        "Le controle estime l'alignement a partir de la geometrie du PDF et peut "
        "etre inconclusif pour les paragraphes courts ou sans couche texte."
    ),
    message="Un paragraphe du contenu semble ne pas etre justifie.",
    kind="field_required",
    severity="warning",
    target=RuleTarget(
        page="all",
        region="full_page",
        page_state="modified",
        excluded_page_types=["TP1", "TP2", "HIGHLIGHTS", "HIGHLIGHTS_PAGE_1"],
    ),
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="paragraph_justification",
        ),
    ],
    failure_message="Un paragraphe du contenu semble ne pas etre justifie.",
    translations={
        "en": {
            "description": (
                "On modified pages, multiline body paragraphs must be visually "
                "aligned on both the left and right, except for the final line. "
                "Alignment is estimated from PDF geometry and may be inconclusive "
                "for short paragraphs or pages without a text layer."
            ),
            "message": "A body paragraph appears not to be justified.",
        }
    },
)

CUSTOM_BAR_PSI_CONVERSION = rule(
    code="CUSTOM_BAR_PSI_CONVERSION",
    name="Pression en bar accompagnee de sa conversion en p.s.i.",
    description=(
        "Toute pression exprimee en bar doit etre suivie entre parentheses "
        "de sa conversion numerique en p.s.i."
    ),
    message="La pression en bar doit etre suivie de sa conversion en p.s.i.",
    kind="field_required",
    severity="error",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="pressure_conversion",
            expected="bar_to_psi",
        ),
    ],
    failure_message=(
        "conversion p.s.i. absente ou incorrecte pour une pression en bar."
    ),
    translations={
        "en": {
            "description": (
                "Every pressure expressed in bar must be followed in parentheses "
                "by its numeric conversion in p.s.i."
            ),
            "message": "A pressure in bar must be followed by its p.s.i. conversion.",
        }
    },
)

CUSTOM_PASCAL_INHG_CONVERSION = rule(
    code="CUSTOM_PASCAL_INHG_CONVERSION",
    name="Pression en pascals accompagnee de sa conversion en inHg",
    description=(
        "Toute pression exprimee en Pa, hPa, kPa, MPa ou GPa doit etre suivie "
        "de sa conversion numerique en inHg entre parentheses."
    ),
    message="La pression en pascals doit etre suivie de sa conversion en inHg.",
    kind="field_required",
    severity="error",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="unit_conversion",
            expected="pascal_to_inhg",
        ),
    ],
    failure_message="conversion inHg absente ou incorrecte pour une pression en pascals.",
    translations={
        "en": {
            "description": (
                "Every pressure expressed in Pa, hPa, kPa, MPa, or GPa must be "
                "followed by its numeric conversion in inHg in parentheses."
            ),
            "message": "A pressure in pascals must be followed by its inHg conversion.",
        }
    },
)

CUSTOM_METRIC_LENGTH_INCH_CONVERSION = rule(
    code="CUSTOM_METRIC_LENGTH_INCH_CONVERSION",
    name="Longueur metrique accompagnee de sa conversion en pouces",
    description=(
        "Toute longueur exprimee en mm, cm, m ou km doit etre suivie de sa "
        "conversion numerique en in. entre parentheses."
    ),
    message="La longueur metrique doit etre suivie de sa conversion en in.",
    kind="field_required",
    severity="error",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="unit_conversion",
            expected="metric_length_to_inch",
        ),
    ],
    failure_message="conversion en pouces absente ou incorrecte pour une longueur metrique.",
    translations={
        "en": {
            "description": (
                "Every length expressed in mm, cm, m, or km must be followed by "
                "its numeric conversion in inches in parentheses."
            ),
            "message": "A metric length must be followed by its inch conversion.",
        }
    },
)

CUSTOM_METRIC_MASS_LBF_CONVERSION = rule(
    code="CUSTOM_METRIC_MASS_LBF_CONVERSION",
    name="Masse metrique accompagnee de sa conversion en lb",
    description=(
        "Toute masse exprimee en mg, g, kg ou tonne doit etre suivie entre "
        "parentheses de sa conversion numerique en lb."
    ),
    message="La masse metrique doit etre suivie de sa conversion en lb.",
    kind="field_required",
    severity="error",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="unit_conversion",
            expected="metric_mass_to_lb",
        ),
    ],
    failure_message="conversion lb absente ou incorrecte pour une masse metrique.",
    translations={
        "en": {
            "description": (
                "Every mass expressed in mg, g, kg, or tonnes must be followed by "
                "its numeric conversion in lb in parentheses."
            ),
            "message": "A metric mass must be followed by its conversion in lb.",
        }
    },
)

CUSTOM_METRIC_TORQUE_LBF_IN_CONVERSION = rule(
    code="CUSTOM_METRIC_TORQUE_LBF_IN_CONVERSION",
    name="Couple metrique accompagne de sa conversion en lbf.in",
    description=(
        "Tout couple exprime en N.m, daN.m ou kN.m doit etre suivi de sa "
        "conversion numerique en lbf.in entre parentheses."
    ),
    message="Le couple metrique doit etre suivi de sa conversion en lbf.in.",
    kind="field_required",
    severity="error",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="unit_conversion",
            expected="metric_torque_to_lbf_in",
        ),
    ],
    failure_message="conversion lbf.in absente ou incorrecte pour un couple metrique.",
    translations={
        "en": {
            "description": (
                "Every torque expressed in N.m, daN.m, or kN.m must be followed "
                "by its numeric conversion in lbf.in in parentheses."
            ),
            "message": "A metric torque must be followed by its lbf.in conversion.",
        }
    },
)

CUSTOM_REPAIR_NOTE = rule(
    code="CUSTOM_REPAIR_NOTE",
    name="Introduction et categories obligatoires dans les NOTE des pages REPAIR",
    description=(
        "Chaque page REPAIR doit commencer sa NOTE par l'introduction "
        "operationnelle attendue et contenir les categories Pressure et "
        "Relative humidity avec la valeur de reference."
    ),
    message=(
        "L'introduction ou les categories NOTE de la page REPAIR sont absentes "
        "ou incorrectes."
    ),
    kind="field_required",
    severity="error",
    target=RuleTarget(page="all", region="full_page", page_type="REPAIR"),
    checks=[
        _required_note_check(
            _NOTE_PRESSURE_PATTERN,
            display="Pressure:",
            page_type="REPAIR",
        ),
        _required_note_check(
            _REPAIR_RELATIVE_HUMIDITY_PATTERN,
            display=_REPAIR_RELATIVE_HUMIDITY,
            page_type="REPAIR",
        ),
    ],
    failure_message="introduction ou categories NOTE REPAIR non conformes.",
    translations={
        "en": {
            "description": (
                "Each REPAIR page must start its NOTE with the expected operational "
                "introduction and contain the Pressure and Relative humidity "
                "categories with their reference values."
            ),
            "message": "The REPAIR NOTE introduction or categories are missing or incorrect.",
        }
    },
)

CUSTOM_TESTING_NOTE = rule(
    code="CUSTOM_TESTING_NOTE",
    name="Introduction et categories obligatoires dans les NOTE des pages TESTING",
    description=(
        "Chaque page TESTING doit commencer sa NOTE par l'introduction "
        "operationnelle attendue et contenir les categories Pressure, Relative "
        "humidity et Temperature."
    ),
    message=(
        "L'introduction ou les categories NOTE de la page TESTING sont absentes "
        "ou incorrectes."
    ),
    kind="field_required",
    severity="error",
    target=RuleTarget(page="all", region="full_page", page_type="TESTING"),
    checks=[
        _required_note_check(
            _NOTE_PRESSURE_PATTERN,
            display="Pressure:",
            page_type="TESTING",
        ),
        _required_note_check(
            _REPAIR_RELATIVE_HUMIDITY_PATTERN,
            display=_REPAIR_RELATIVE_HUMIDITY,
            page_type="TESTING",
        ),
        _required_note_check(
            r"\bTemperature\b",
            display="Temperature",
            page_type="TESTING",
        ),
    ],
    failure_message="introduction ou categories NOTE TESTING non conformes.",
    translations={
        "en": {
            "description": (
                "Each TESTING page must start its NOTE with the expected operational "
                "introduction and contain the Pressure, Relative humidity, and "
                "Temperature categories."
            ),
            "message": "The TESTING NOTE introduction or categories are missing or incorrect.",
        }
    },
)

CUSTOM_STORAGE_NOTE = rule(
    code="CUSTOM_STORAGE_NOTE",
    name="Introduction et categories obligatoires dans les NOTE des pages STORAGE",
    description=(
        "Chaque page STORAGE doit commencer sa NOTE par l'introduction "
        "operationnelle attendue et contenir les categories Pressure, Relative "
        "humidity et Temperature avec les valeurs de reference."
    ),
    message=(
        "L'introduction ou les categories NOTE de la page STORAGE sont absentes "
        "ou incorrectes."
    ),
    kind="field_required",
    severity="error",
    target=RuleTarget(page="all", region="full_page", page_type="STORAGE"),
    checks=[
        _required_note_check(
            _NOTE_PRESSURE_PATTERN,
            display="Pressure:",
            page_type="STORAGE",
        ),
        _required_note_check(
            _REPAIR_RELATIVE_HUMIDITY_PATTERN,
            display=_REPAIR_RELATIVE_HUMIDITY,
            page_type="STORAGE",
        ),
        _required_note_check(
            _STORAGE_TEMPERATURE_PATTERN,
            display=_STORAGE_TEMPERATURE,
            page_type="STORAGE",
            anchor=r"(?i)\bRelative\s+humidity\s*:",
            anchor_position="below",
        ),
    ],
    failure_message="introduction ou categories NOTE STORAGE non conformes.",
    translations={
        "en": {
            "description": (
                "Each STORAGE page must start its NOTE with the expected operational "
                "introduction and contain the Pressure, Relative humidity, and "
                "Temperature categories with their reference values."
            ),
            "message": "The STORAGE NOTE introduction or categories are missing or incorrect.",
        }
    },
)

CUSTOM_TP1_THALES_ADDRESS = rule(
    code="CUSTOM_TP1_THALES_ADDRESS",
    name="Adresse THALES exacte sur les pages TP1",
    description=(
        "Chaque page identifiee TP1 doit contenir exactement l'adresse THALES "
        "de reference."
    ),
    message="L'adresse THALES de la page TP1 est absente ou incorrecte.",
    kind="field_required",
    severity="warning",
    target=RuleTarget(page="all", region="full_page", page_type="TP1"),
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=pattern,
            require_all=True,
            expected_display=display,
            suggestion_mode="fuzzy",
            missing_anchor=(
                _THALES_TP1_ADDRESS_ELEMENTS[index + 1][0]
                if index + 1 < len(_THALES_TP1_ADDRESS_ELEMENTS)
                else _THALES_TP1_ADDRESS_ELEMENTS[index - 1][0]
            ),
            missing_anchor_position=(
                "above" if index + 1 < len(_THALES_TP1_ADDRESS_ELEMENTS) else "below"
            ),
        )
        for index, (pattern, display) in enumerate(_THALES_TP1_ADDRESS_ELEMENTS)
    ],
    failure_message="adresse THALES non conforme.",
    translations={
        "en": {
            "description": "Every page identified as TP1 must contain the exact reference THALES address.",
            "message": "The THALES address on the TP1 page is missing or incorrect.",
        }
    },
)

CUSTOM_TP1_THALES_LOGO_FONT_SIZE = rule(
    code="CUSTOM_TP1_THALES_LOGO_FONT_SIZE",
    name="Taille du logo THALES sur les pages TP1",
    description=(
        "Le T de la police Thales en debut de page TP1 doit avoir une taille "
        "de 36 pt."
    ),
    message="La taille du logo THALES sur TP1 n'est pas 36 pt.",
    kind="field_required",
    severity="warning",
    target=RuleTarget(page="all", region="full_page", page_type="TP1"),
    checks=[
        Check(
            field="thales_logo_t",
            operator="font_size_equals",
            expected=36,
            require_all=True,
        ),
    ],
    failure_message="taille du logo THALES non conforme sur TP1.",
    translations={
        "en": {
            "description": "The Thales T at the start of a TP1 page must use a 36 pt font.",
            "message": "The THALES logo size on TP1 is not 36 pt.",
        }
    },
)

CUSTOM_TP2_IMPORTANT_NOTICE = rule(
    code="CUSTOM_TP2_IMPORTANT_NOTICE",
    name="Important Notice TP2 conforme au modele ATA100",
    description=(
        "Le bloc IMPORTANT NOTICE de la page TP2 doit correspondre exactement "
        "au modele ATA100, hors differences de retours a la ligne et d'espaces."
    ),
    message="L'Important Notice de la page TP2 n'est pas conforme au modele ATA100.",
    kind="field_required",
    severity="error",
    target=_TP2_TARGET,
    checks=[
        Check(
            field="important_notice",
            operator="normalized_equals",
            expected=IMPORTANT_NOTICE_TEXT,
            normalization=["unicode", "spaces", "line_breaks", "trim"],
        ),
    ],
    failure_message="Important Notice TP2 non conforme au modele ATA100.",
    translations={
        "en": {
            "description": (
                "The IMPORTANT NOTICE block on TP2 must exactly match the ATA100 "
                "template, apart from line-break and space differences."
            ),
            "message": "The TP2 Important Notice does not match the ATA100 template.",
        }
    },
)

CUSTOM_TITLE_PAGE_COPYRIGHT = rule(
    code="CUSTOM_TITLE_PAGE_COPYRIGHT",
    name="Copyright du footer conforme a l'annee de revision",
    description=(
        "Le footer des pages modifiees doit contenir le texte integral du "
        "copyright THALES de reference. L'annee de debut doit correspondre a "
        "l'annee de premiere issue et l'annee de fin a l'annee de revision du document."
    ),
    message="Le copyright du footer est absent ou une annee est incorrecte.",
    kind="field_required",
    severity="warning",
    target=_MODIFIED_FOOTER_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=_COPYRIGHT_PATTERN,
        ),
        Check(
            field="copyright_start_year",
            operator="equals_field",
            compare_to=FieldRef(
                source="document_meta",
                field="meta_first_issue_date",
                normalization=["extract_year"],
            ),
        ),
        Check(
            field="copyright_end_year",
            operator="equals_field",
            compare_to=FieldRef(
                source="document_meta",
                field="meta_revision_date",
                normalization=["extract_year"],
            ),
        ),
    ],
    failure_message="Copyright du footer non conforme",
    translations={
        "en": {
            "description": (
                "The footer of pages modified by the revision must contain the "
                "full reference THALES copyright text. Its start year must match "
                "the first issue year, and its end year the document revision year."
            ),
            "message": "The footer copyright is missing or contains an incorrect year.",
        }
    },
)

CUSTOM_COPYRIGHT_POSITION = rule(
    code="CUSTOM_COPYRIGHT_POSITION",
    name="Position du copyright selon la parite de page",
    description=(
        "Sur chaque page PDF, le coin superieur gauche du copyright THALES "
        "doit etre a x=3.03 cm sur les pages impaires et x=1.76 cm sur les "
        "pages paires, avec y=26.51 cm. La tolerance est de 0.10 cm."
    ),
    message="Le copyright est absent ou mal positionne.",
    kind="field_required",
    severity="warning",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="copyright_position",
        ),
    ],
    failure_message="Position du copyright non conforme a la parite de page.",
    translations={
        "en": {
            "description": (
                "On every PDF page, the upper-left corner of the THALES "
                "copyright must be at x=3.03 cm on odd pages and x=1.76 cm "
                "on even pages, with y=26.51 cm. Tolerance is 0.10 cm."
            ),
            "message": "The copyright is missing or incorrectly positioned.",
        }
    },
)

CUSTOM_PAGE_CONTENT_POSITION = rule(
    code="CUSTOM_PAGE_CONTENT_POSITION",
    name="Position du contenu selon la parite de page",
    description=(
        "Sur chaque page PDF, la marge gauche mediane du contenu (hors ligne "
        "copyright) doit etre a x=3.03 cm sur les pages impaires et x=1.76 cm "
        "sur les pages paires. La tolerance est de 0.10 cm."
    ),
    message="Le contenu est mal positionne selon la parite de page.",
    kind="field_required",
    severity="warning",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="page_content_position",
        ),
    ],
    failure_message="Position du contenu non conforme a la parite de page.",
    translations={
        "en": {
            "description": (
                "On every PDF page, the median left margin of the content "
                "(excluding the copyright line) must be x=3.03 cm on odd pages "
                "and x=1.76 cm on even pages. Tolerance is 0.10 cm."
            ),
            "message": "The content is incorrectly positioned for its page parity.",
        }
    },
)

CUSTOM_PDF_BOOKMARK_TITLE_MATCH = rule(
    code="CUSTOM_PDF_BOOKMARK_TITLE_MATCH",
    name="Titre des signets PDF present sur la page cible",
    description=(
        "Le titre de chaque signet PDF doit apparaitre dans le texte de la page "
        "vers laquelle le signet renvoie."
    ),
    message="Le titre du signet PDF ne correspond pas au contenu de sa page cible.",
    kind="field_required",
    severity="warning",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="pdf_bookmarks",
        )
    ],
    failure_message="Le titre d'un signet PDF est absent de sa page cible.",
    translations={
        "en": {
            "description": (
                "The title of each PDF bookmark must appear in the text of its "
                "destination page."
            ),
            "message": "The PDF bookmark title does not match the content of its destination page.",
        }
    },
)

CUSTOM_NO_DEGREE_C_SYMBOL = rule(
    code="CUSTOM_NO_DEGREE_C_SYMBOL",
    name="Unite de temperature C ecrite au format deg. C",
    description="Le symbole °C doit etre ecrit sous la forme deg. C.",
    message="Le symbole °C est interdit : utiliser deg. C.",
    kind="regex_flag",
    severity="info",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex",
            expected=r"(?i)°\s*C\b",
            replacement="deg. C",
        ),
    ],
    failure_message="unite °C interdite, utiliser deg. C.",
    translations={
        "en": {
            "description": "The °C symbol must be written as deg. C.",
            "message": "The °C symbol is forbidden: use deg. C.",
        }
    },
)

CUSTOM_NO_DEGREE_F_SYMBOL = rule(
    code="CUSTOM_NO_DEGREE_F_SYMBOL",
    name="Unite de temperature F ecrite au format deg. F",
    description="Le symbole °F doit etre ecrit sous la forme deg. F.",
    message="Le symbole °F est interdit : utiliser deg. F.",
    kind="regex_flag",
    severity="info",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex",
            expected=r"(?i)°\s*F\b",
            replacement="deg. F",
        ),
    ],
    failure_message="unite °F interdite, utiliser deg. F.",
    translations={
        "en": {
            "description": "The °F symbol must be written as deg. F.",
            "message": "The °F symbol is forbidden: use deg. F.",
        }
    },
)

CUSTOM_DECIMAL_COMMA = rule(
    code="CUSTOM_DECIMAL_COMMA",
    name="Valeurs decimales doivent etre separees par un point",
    description=(
        "Les valeurs numeriques decimales des pages modifiees doivent utiliser "
        "un point comme separateur decimal, et non une virgule."
    ),
    message="Une valeur decimale utilise une virgule au lieu d'un point.",
    kind="regex_flag",
    severity="warning",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex",
            expected=r"(?<!\d)(\d+),(\d+)(?!\d)",
            replacement=r"\1.\2",
        ),
    ],
    translations={
        "en": {
            "description": (
                "Decimal numeric values on modified pages must use a point "
                "rather than a comma as the decimal separator."
            ),
            "message": "A decimal value uses a comma instead of a point.",
        }
    },
)

CUSTOM_TEMPERATURE_FAHRENHEIT = rule(
    code="CUSTOM_TEMPERATURE_FAHRENHEIT",
    name="Temperature en deg. C accompagnee de sa conversion en deg. F",
    description=(
        "Toute temperature exprimee en deg. C doit etre suivie de sa "
        "conversion numerique en deg. F entre parentheses."
    ),
    message="La temperature en deg. C doit etre suivie de sa conversion en deg. F.",
    kind="regex_flag",
    severity="error",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex",
            expected=_TEMPERATURE_WITHOUT_FAHRENHEIT_PATTERN,
            replacement="{{temperature_fahrenheit}}",
        ),
    ],
    failure_message="conversion Fahrenheit absente pour la temperature.",
    translations={
        "en": {
            "description": (
                "Every temperature expressed in deg. C must be followed by "
                "its numeric conversion in deg. F in parentheses."
            ),
            "message": "A temperature in deg. C must be followed by its conversion in deg. F.",
        }
    },
)

CUSTOM_TEMPERATURE_RANGE_FORMAT = rule(
    code="CUSTOM_TEMPERATURE_RANGE_FORMAT",
    name="Plages de temperature au format X to X deg. C",
    description=(
        "Une plage de temperature Celsius doit s'ecrire X to X deg. C : l'unite "
        "apparait apres la seconde valeur, sans C au milieu."
    ),
    message="La plage de temperature doit etre au format X to X deg. C.",
    kind="regex_flag",
    severity="error",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex",
            expected=_TEMPERATURE_RANGE_UNIT_IN_MIDDLE_PATTERN,
        ),
        Check(
            field="text",
            operator="regex",
            expected=_TEMPERATURE_RANGE_MISSING_CELSIUS_PATTERN,
        ),
    ],
    failure_message="Plage de temperature Celsius hors du format X to X deg. C.",
    translations={
        "en": {
            "description": (
                "A Celsius temperature range must use X to X deg. C: the unit "
                "appears after the second value, with no C in the middle."
            ),
            "message": "The temperature range must use the X to X deg. C format.",
        }
    },
)

CUSTOM_FORBIDDEN_CONSUMABLES = rule(
    code="CUSTOM_FORBIDDEN_CONSUMABLES",
    name="Consommables a supprimer",
    description="Les references aux consommables interdits doivent etre supprimees.",
    message="Consommable a supprimer.",
    kind="regex_flag",
    severity="error",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="contains_none",
            expected=["Silica gel", "dessicant bag", "desiccant", "freon", "flugene"],
            replacement="",
        ),
    ],
    failure_message="consommable a supprimer.",
    translations={
        "en": {
            "description": "References to forbidden consumables must be removed.",
            "message": "Consumable to remove.",
        }
    },
)

CUSTOM_REPLACE_LEGACY_NAMES = rule(
    code="CUSTOM_REPLACE_LEGACY_NAMES",
    name="References historiques a remplacer par THALES",
    description=(
        "Les references a AVIONICS, SEXTANT et THOMSON doivent etre remplacees "
        "par THALES."
    ),
    message="Reference historique a remplacer par THALES.",
    kind="regex_flag",
    severity="warning",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex",
            expected=r"(?i)\b(?:AVIONICS|SEXTANT|THOMSON)\b",
            replacement="THALES",
        ),
    ],
    failure_message="reference historique a remplacer par THALES.",
    translations={
        "en": {
            "description": (
                "References to AVIONICS, SEXTANT, and THOMSON must be replaced "
                "with THALES."
            ),
            "message": "A legacy reference must be replaced with THALES.",
        }
    },
)

CUSTOM_LETTER_DIGIT_CONFUSION = rule(
    code="CUSTOM_LETTER_DIGIT_CONFUSION",
    name="Confusion entre lettres et chiffres",
    description=(
        "Repere un chiffre utilise dans un mot a la place d'une lettre, "
        "et les lettres O, I ou l utilisees dans une sequence numerique."
    ),
    message="Une confusion entre lettre et chiffre est a verifier.",
    kind="regex_flag",
    severity="warning",
    target=_MODIFIED_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex",
            expected=_LETTER_DIGIT_CONFUSION_PATTERN,
        ),
    ],
    failure_message="confusion possible entre lettres et chiffres.",
    translations={
        "en": {
            "description": (
                "Flags a digit used in a word in place of a letter, and O, I, or l "
                "used in a numeric sequence."
            ),
            "message": "A possible letter/digit confusion needs review.",
        }
    },
)

CUSTOM_REVISION_LEP_STAR = rule(
    code="CUSTOM_REVISION_LEP_STAR",
    name="Etoile LEP presente pour chaque page revisee ou nouvelle",
    description=(
        "Toute page declaree revisee (R) ou nouvelle (N) dans les Highlights "
        "doit porter une etoile apres sa date dans la liste des pages effectives."
    ),
    message="Page revisee dans les Highlights sans etoile dans la LEP.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "lep_star"},
        )
    ],
    failure_message="etoile absente dans la liste des pages effectives.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "Every page declared revised (R) or new (N) in Highlights must have "
                "a star after its date in the list of effective pages."
            ),
            "message": "A page revised in Highlights has no star in the LEP.",
        }
    },
)

CUSTOM_REVISION_UNDECLARED_STAR = rule(
    code="CUSTOM_REVISION_UNDECLARED_STAR",
    name="Etoile LEP justifiee par un statut R ou N dans les Highlights",
    description=(
        "Une etoile dans la liste des pages effectives signale une page modifiee : "
        "cette page doit etre declaree R ou N dans les Highlights."
    ),
    message="Etoile LEP sur une page non declaree revisee dans les Highlights.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "undeclared_star"},
        )
    ],
    failure_message="etoile LEP sans statut R ou N dans les Highlights.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "A star in the list of effective pages marks a modified page; that "
                "page must be declared R or N in Highlights."
            ),
            "message": "The LEP has a star on a page not declared revised in Highlights.",
        }
    },
)

CUSTOM_REVISION_HIGHLIGHTS_STATUS = rule(
    code="CUSTOM_REVISION_HIGHLIGHTS_STATUS",
    name="Designation Highlights coherente avec la LEP et le pied de page",
    description=(
        "La colonne Designation doit utiliser R, N, U ou D. Le controle verifie "
        "la coherence des statuts avec la LEP et le pied de page. Si le PDF N-1 "
        "est fourni, N doit etre absent de sa LEP, tandis que R, U et D doivent "
        "y figurer; une page D ne doit plus figurer dans la LEP ni le document courant."
    ),
    message="La designation Highlights est incoherente avec les pages effectives.",
    kind="field_required",
    severity="warning",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "highlights_status_consistency"},
        )
    ],
    failure_message=(
        "designation Highlights invalide ou incoherente avec la LEP, le pied de "
        "page ou la presence de la page."
    ),
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "Highlights Designation must be R, N, U, or D. The designation must "
                "agree with the LEP and footer; a D page must no longer appear in "
                "the current LEP or document. When the previous PDF is provided, "
                "N must be absent from its LEP, while R, U, and D must be present."
            ),
            "message": "The Highlights designation conflicts with the effective-page evidence.",
        }
    },
)

CUSTOM_HIGHLIGHTS_DESIGNATION_REQUIRED = rule(
    code="CUSTOM_HIGHLIGHTS_DESIGNATION_REQUIRED",
    name="Designation obligatoire pour chaque ligne de pages des Highlights",
    description=(
        "Chaque ligne des Highlights qui contient une plage de pages doit avoir "
        "une designation R, N, U ou D."
    ),
    message="Une ligne de pages des Highlights n'a pas de designation.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "highlights_designation_required"},
        )
    ],
    failure_message="Designation absente pour une ligne de pages des Highlights.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "Every Highlights row containing a page range must have an "
                "R, N, U, or D designation."
            ),
            "message": "A Highlights page row is missing its designation.",
        }
    },
)

CUSTOM_HIGHLIGHTS_CHAPTER = rule(
    code="CUSTOM_HIGHLIGHTS_CHAPTER",
    name="Intitule de chapitre autorise dans les Highlights",
    description=(
        "Chaque chapitre ou section des Highlights doit utiliser l'un des "
        "intitules autorises du catalogue THALES."
    ),
    message="Un chapitre des Highlights n'est pas autorise.",
    kind="field_required",
    severity="error",
    target=_HIGHLIGHTS_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "highlights_chapter"},
        )
    ],
    failure_message="intitule de chapitre non autorise dans les Highlights.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "Every chapter or section in Highlights must use one of the "
                "chapter titles authorized by the THALES catalog."
            ),
            "message": "A Highlights chapter title is not authorized.",
        }
    },
)

CUSTOM_REVISION_LEP_BLANK_STAR = rule(
    code="CUSTOM_REVISION_LEP_BLANK_STAR",
    name="Etoile LEP des pages Blank selon le statut New de la page impaire",
    description=(
        "Une entree Blank dans la LEP porte une etoile uniquement lorsque la page "
        "impaire de son couple est declaree N (New) dans les Highlights. Une page "
        "declaree R (Modify), inchangee ou sans statut N ne doit pas porter d'etoile."
    ),
    message="Etoile de page Blank incoherente avec le statut de sa page impaire.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "blank_lep_star"},
        )
    ],
    failure_message="etoile de page Blank incoherente avec le statut New de sa page impaire.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "A Blank entry in the LEP has a star only when the odd page in its "
                "pair is declared N (New) in Highlights. A page declared R (Modify), "
                "unchanged, or without an N status must not have a star."
            ),
            "message": "The Blank page star is inconsistent with its odd page's status.",
        }
    },
)

CUSTOM_REVISION_LEP_DATE = rule(
    code="CUSTOM_REVISION_LEP_DATE",
    name="Date LEP conforme au statut de la page",
    description=(
        "La date de la liste des pages effectives doit valoir la date de revision "
        "du mapping pour une page revisee ou nouvelle, et rester la derniere date "
        "d'emission connue pour une page inchangee."
    ),
    message="Date LEP incoherente avec le statut de la page.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "lep_date"},
        )
    ],
    failure_message="date LEP incoherente avec le statut de la page.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "For a revised or new page, the list of effective pages date must "
                "equal the mapped revision date and remain the latest known issue "
                "date for an unchanged page."
            ),
            "message": "The LEP date is inconsistent with the page status.",
        }
    },
)

CUSTOM_REVISION_FOOTER_DATE = rule(
    code="CUSTOM_REVISION_FOOTER_DATE",
    name="Date du pied de page conforme aux Highlights et a la LEP",
    description=(
        "Le pied de page doit porter la date de revision du mapping pour une page "
        "revisee ou nouvelle, et la date declaree dans la liste des pages "
        "effectives pour une page inchangee."
    ),
    message="Date du pied de page incoherente avec les Highlights et la LEP.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "footer_date"},
        )
    ],
    failure_message="date du pied de page incoherente avec les Highlights et la LEP.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "The footer must show the mapped revision date for a revised or new "
                "page, and the date declared in the list of effective pages for an "
                "unchanged page."
            ),
            "message": "The footer date is inconsistent with Highlights and the LEP.",
        }
    },
)

CUSTOM_REVISION_UNDECLARED_PAGE = rule(
    code="CUSTOM_REVISION_UNDECLARED_PAGE",
    name="Page datee de la revision declaree modifiee",
    description=(
        "Une page qui porte la date de la revision courante doit etre declaree "
        "modifiee, dans les Highlights (R ou N) et par une etoile dans la LEP."
    ),
    message="Page datee de la revision courante sans declaration de modification.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "undeclared_page"},
        )
    ],
    failure_message="page datee de la revision courante sans declaration de modification.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "A page carrying the current revision date must be declared modified "
                "in Highlights (R or N) and marked with a star in the LEP."
            ),
            "message": "A page dated with the current revision has no modification declaration.",
        }
    },
)

CUSTOM_REVISION_PAGE_NOT_IN_LEP = rule(
    code="CUSTOM_REVISION_PAGE_NOT_IN_LEP",
    name="Page du document presente dans la liste des pages effectives",
    description="Toute page du document doit figurer dans la liste des pages effectives.",
    message="Page du document absente de la liste des pages effectives.",
    kind="field_required",
    severity="warning",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "page_not_in_lep"},
        )
    ],
    failure_message="page du document absente de la liste des pages effectives.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": "Every page in the document must appear in the list of effective pages.",
            "message": "The document page is missing from the list of effective pages.",
        }
    },
)

CUSTOM_REVISION_MODIFIED_PAGE_ABSENT = rule(
    code="CUSTOM_REVISION_MODIFIED_PAGE_ABSENT",
    name="Page declaree revisee presente dans le document",
    description=(
        "Toute page declaree revisee ou nouvelle dans les Highlights doit exister "
        "dans le document et s'identifier dans son pied de page."
    ),
    message="Page declaree revisee introuvable dans le document.",
    kind="field_required",
    severity="warning",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "modified_page_absent"},
        )
    ],
    failure_message="page declaree revisee introuvable dans le document.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "Every page declared revised or new in Highlights must exist in the "
                "document and be identified in its footer."
            ),
            "message": "The page declared revised cannot be found in the document.",
        }
    },
)

CUSTOM_HIGHLIGHTS_PAGE_PAIRING = rule(
    code="CUSTOM_HIGHLIGHTS_PAGE_PAIRING",
    name="Pages Highlights declarees par couple impaire/paire",
    description=(
        "Les Highlights declarent les pages par couple : une page impaire est "
        "suivie de la page paire correspondante, et une page paire est precedee "
        "de son impaire."
    ),
    message="Page Highlights declaree sans sa page paire ou impaire associee.",
    kind="field_required",
    severity="warning",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "highlights_pairing"},
        )
    ],
    failure_message="page Highlights declaree sans sa page paire ou impaire associee.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "Highlights declare pages in pairs: an odd page is followed by its "
                "corresponding even page, and an even page is preceded by its odd page."
            ),
            "message": "A Highlights page is declared without its corresponding odd or even page.",
        }
    },
)

CUSTOM_HIGHLIGHTS_PAGE_LABEL_FORMAT = rule(
    code="CUSTOM_HIGHLIGHTS_PAGE_LABEL_FORMAT",
    name="Libelle Page/Pages et alignement dans les Highlights",
    description=(
        "Une plage de pages s'ecrit \u00ab Pages 701 to 704 \u00bb et une page unique "
        "\u00ab Page  401 \u00bb, avec deux espaces pour conserver l'alignement des "
        "numeros."
    ),
    message="Libelle Page/Pages ou alignement non conforme dans les Highlights.",
    kind="field_required",
    severity="warning",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "highlights_page_label"},
        )
    ],
    failure_message="libelle Page/Pages ou alignement non conforme dans les Highlights.",
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "A page range is written as 'Pages 701 to 704' and a single page as "
                "'Page  401', with two spaces to preserve number alignment."
            ),
            "message": "The Page/Pages label or alignment is not compliant in Highlights.",
        }
    },
)

CUSTOM_ROR_INSERTION_DATE = rule(
    code="CUSTOM_ROR_INSERTION_DATE",
    name="Date d'insertion du Record of Revisions conforme a la date de revision",
    description=(
        "Dans le Record of Revisions, la date d'insertion doit reprendre le mois "
        "de la date de revision si le jour est inferieur a 15, sinon le mois suivant."
    ),
    message="La date d'insertion du Record of Revisions est incoherente.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "ror_insertion_date"},
        )
    ],
    failure_message=(
        "date d'insertion du Record of Revisions incoherente avec la date de revision."
    ),
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "In the Record of Revisions, the insertion date must use the revision "
                "month when the revision day is below 15, otherwise the following month."
            ),
            "message": "The Record of Revisions insertion date is inconsistent with the revision date.",
        }
    },
)

CUSTOM_ROR_REVISION_DATE = rule(
    code="CUSTOM_ROR_REVISION_DATE",
    name="Date de revision du Record of Revisions conforme aux Highlights",
    description=(
        "La date de revision la plus recente du Record of Revisions doit "
        "correspondre a la date de revision des Highlights."
    ),
    message="La date de revision du Record of Revisions est incoherente avec les Highlights.",
    kind="field_required",
    severity="error",
    target=_ALL_PAGE_TARGET,
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="revision_consistency",
            operation_params={"control": "ror_revision_date"},
        )
    ],
    failure_message=(
        "date de revision du Record of Revisions incoherente avec les Highlights."
    ),
    only_if=Condition(field="meta_revision_date", state="present"),
    translations={
        "en": {
            "description": (
                "The current revision date in the Record of Revisions must match the "
                "revision date used by the Highlights."
            ),
            "message": "The current Record of Revisions date does not match the Highlights revision date.",
        }
    },
)

REVISION_RULE_DEFINITIONS = (
    CUSTOM_REVISION_LEP_STAR,
    CUSTOM_REVISION_UNDECLARED_STAR,
    CUSTOM_REVISION_HIGHLIGHTS_STATUS,
    CUSTOM_HIGHLIGHTS_DESIGNATION_REQUIRED,
    CUSTOM_HIGHLIGHTS_CHAPTER,
    CUSTOM_REVISION_LEP_BLANK_STAR,
    CUSTOM_REVISION_LEP_DATE,
    CUSTOM_REVISION_FOOTER_DATE,
    CUSTOM_FOOTER_PAGE_NUMBER,
    CUSTOM_REVISION_UNDECLARED_PAGE,
    CUSTOM_REVISION_PAGE_NOT_IN_LEP,
    CUSTOM_REVISION_MODIFIED_PAGE_ABSENT,
    CUSTOM_HIGHLIGHTS_PAGE_PAIRING,
    CUSTOM_HIGHLIGHTS_PAGE_LABEL_FORMAT,
    CUSTOM_ROR_INSERTION_DATE,
    CUSTOM_ROR_REVISION_DATE,
)

RULE_DEFINITIONS = (
    *REVISION_RULE_DEFINITIONS,
    CUSTOM_CMM_NUMBER,
    CUSTOM_CMM_NUMBER_FONT_SIZE,
    CUSTOM_THALES_LOGO_FONT_SIZE,
    CUSTOM_TP1_THALES_LOGO_FONT_SIZE,
    CUSTOM_TP2_IMPORTANT_NOTICE,
    CUSTOM_TITLE_PAGE_COPYRIGHT,
    CUSTOM_COPYRIGHT_POSITION,
    CUSTOM_PAGE_CONTENT_POSITION,
    CUSTOM_PDF_BOOKMARK_TITLE_MATCH,
    CUSTOM_TP1_REVISION_NUMBER,
    CUSTOM_TP1_FIRST_ISSUE_DATE,
    CUSTOM_HIGHLIGHTS_REVISION_HEADER,
    CUSTOM_HIGHLIGHTS_DELETION_DESCRIPTION,
    CUSTOM_HIGHLIGHTS_REVISED_DESCRIPTION,
    CUSTOM_CHAPTER_NUMBER_SEQUENCE,
    CUSTOM_LIST_OF_MATERIALS_CODE_NO_PARENTHESES,
    CUSTOM_LIST_OF_MATERIALS_CODE_LOWERCASE,
    CUSTOM_LIST_OF_MATERIALS_SUPPLIER_FSCM,
    CUSTOM_REVISION_BAR_NEW_PAGE,
    CUSTOM_REVISION_BAR_MODIFIED_PAGE,
    CUSTOM_REVISION_BAR_MARGIN_POSITION,
    CUSTOM_TP1_REVISION_BAR_FOOTER,
    CUSTOM_TP2_REVISION_BAR_BODY_ONLY,
    CUSTOM_VENDOR_CODE_LIST_REFERENCE,
    CUSTOM_NI_PART_NUMBER_ORDER,
    CUSTOM_INTRODUCTION_SHOP_VERIFICATION,
    CUSTOM_HIGHLIGHTS_HOLDER,
    CUSTOM_HIGHLIGHTS_ATA_NUMBER,
    CUSTOM_HIGHLIGHTS_PNR_HEADER,
    CUSTOM_HEADER_DOCUMENT_TYPE,
    CUSTOM_TP1_HEADER_DOCUMENT_TYPE,
    CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE,
    CUSTOM_HIGHLIGHTS_LEGEND_FOOTER,
    CUSTOM_PNR_PAGE_VALUE,
    CUSTOM_TP1_PNR_PAGE_VALUE,
    CUSTOM_REPAIR_NOTE,
    CUSTOM_TESTING_NOTE,
    CUSTOM_STORAGE_NOTE,
    CUSTOM_TP1_THALES_ADDRESS,
    CUSTOM_DECIMAL_COMMA,
    CUSTOM_SENTENCE_PUNCTUATION,
    CUSTOM_ENUMERATION_PUNCTUATION_SWAP,
    CUSTOM_PARAGRAPH_JUSTIFICATION,
    CUSTOM_TEMPERATURE_FAHRENHEIT,
    CUSTOM_TEMPERATURE_RANGE_FORMAT,
    CUSTOM_BAR_PSI_CONVERSION,
    CUSTOM_PASCAL_INHG_CONVERSION,
    CUSTOM_METRIC_LENGTH_INCH_CONVERSION,
    CUSTOM_METRIC_MASS_LBF_CONVERSION,
    CUSTOM_METRIC_TORQUE_LBF_IN_CONVERSION,
    CUSTOM_FORBIDDEN_CONSUMABLES,
    CUSTOM_REPLACE_LEGACY_NAMES,
    CUSTOM_LETTER_DIGIT_CONFUSION,
    CUSTOM_NO_DEGREE_C_SYMBOL,
    CUSTOM_NO_DEGREE_F_SYMBOL,
)

RULE_METADATA = {
    definition.code: definition.metadata
    for definition in RULE_DEFINITIONS
}
CATALOG = {
    _CATALOG_VERSION: [definition.compiled_rule for definition in RULE_DEFINITIONS]
}
STANDARD_SPEC: dict[str, object] = {
    "code": _STANDARD_CODE,
    "label": "THALES - Regles utilisateur",
    "description": "Regles locales editables pour les controles documentaires THALES.",
    "versions": CATALOG,
    "metadata": RULE_METADATA,
}