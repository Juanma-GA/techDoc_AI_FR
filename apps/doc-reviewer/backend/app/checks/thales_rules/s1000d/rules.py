"""THALES S1000D rule definitions, built through the same factory as the ATA100 norm.

Source: "règles S1000D.xlsx" (rules marked "manuel" are excluded: they cannot be
checked deterministically). The numbers in the comments are the Excel numbers.
Structure-dependent controls live in `operations.py` (`s1000d_*` operations).
"""

from __future__ import annotations

from functools import partial

from app.checks.thales_rules.rule_factory import build_rule
from app.core.compiled_rules import Check, Condition, RuleTarget

from .highlights_rules import S1000D_HIGHLIGHTS_RFU_STATUS

_STANDARD_CODE = "THALES-S1000D"
_CATALOG_VERSION = "v1"
_TARGET = RuleTarget(page="all", region="full_page")

# Migration/MCO rules only run when the mapping states the update type; 14/15 follow the manufacturer.
_MIGRATION = Condition(field="meta_update_type", equals="Migration")
_MCO = Condition(field="meta_update_type", equals="MCO")
_AIRBUS = Condition(field="meta_manufacturer", equals="Airbus")
_BOEING = Condition(field="meta_manufacturer", equals="Boeing")

rule = partial(build_rule, _STANDARD_CODE, _CATALOG_VERSION)

_DASH = r"[-\u2010-\u2015\u2212\uFFFD]"


def _operation_check(operation: str, control: str) -> Check:
    return Check(
        field="text",
        operator="client_operation",
        operation=operation,
        operation_params={"control": control},
    )


def _dm_status(control: str) -> Check:
    return _operation_check("s1000d_dm_status", control)


def _front_matter(control: str) -> Check:
    return _operation_check("s1000d_front_matter", control)


def _content(control: str) -> Check:
    return _operation_check("s1000d_content", control)


# The published footer prints "©2006-2026 THALES AVS FRANCE SAS This document" (no space after the
# symbol, no full stop after the first company name): both are tolerated, the years are checked apart.
_COPYRIGHT_PATTERN = (
    r"(?i)\u00a9\s*\d{4}\s*-\s*\d{4}\s+"
    r"THALES\s+AVS\s+FRANCE\s+SAS\.?\s+"
    r"This\s+document\s+and\s+any\s+data\s+included\s+are\s+the\s+property\s+of\s+"
    r"THALES\s+AVS\s+FRANCE\s+SAS\.\s+"
    r"They\s+cannot\s+be\s+reproduced,\s+disclosed\s+or\s+used\s+"
    r"without\s+the\s+company's\s+prior\s+written\s+approval\.?"
)
_COPYRIGHT_DISPLAY = (
    "\u00a9 2000-2026 THALES AVS FRANCE SAS. This document and any data included are the "
    "property of THALES AVS FRANCE SAS. They cannot be reproduced, disclosed or used "
    "without the company's prior written approval"
)
_ADDRESS_ELEMENTS: tuple[tuple[str, str], ...] = (
    (r"(?i)75-77\s+AV\s+MARCEL\s+DASSAULT", "75-77 AV MARCEL DASSAULT"),
    (r"(?i)33700\s+MERIGNAC\s+FRANCE", "33700 MERIGNAC FRANCE"),
    (r"(?i)Tel\s*:?\s*05\s+24\s+44\s+77\s+40", "Tel: 05 24 44 77 40"),
    (r"(?i)www\.thalesgroup\.com", "www.thalesgroup.com"),
)
_SPM_TAIL = rf"\s+20-02-00\s*{_DASH}\s*STANDARD\s+PRACTICES\s+MANUAL\s*\(\s*SPM\s*\)"
_SOPM_TAIL = rf"\s+20-02-00\s*{_DASH}\s*STANDARD\s+OVERHAUL\s+PRACTICES\s+MANUAL\s*\(\s*SOPM\s*\)"
_SPM_LINK_PATTERN = rf"(?i:\brefer\s+to)\s+SPM\b(?!{_SPM_TAIL})"
_SOPM_LINK_PATTERN = rf"(?i:\brefer\s+to)\s+SOPM\b(?!{_SOPM_TAIL})"
_SHOP_VERIFICATION_PATTERN = r"(?i)\bShop\s+Verification\b"
# Two layouts: "Not specific-xxxxx" in the tool name, or the published table cell "Not specific"
# whose MFR column is then the LOCAL code printed "Commercially available".
_NOT_SPECIFIC_WITHOUT_LOCAL = (
    r"(?i)(?<!\bLOCAL\b[^\n]*)\bNot\s+sp[e\u00e9]cific\s*[-\u2010-\u2015\u2212]\s*\w+"
    r"(?![^\n]*\bLOCAL\b)(?![^\n]*\n[^\n]*\bLOCAL\b)"
    r"|(?m:^[ \t]*Not[ \t]+sp[e\u00e9]cific[ \t]*$)(?!\s*(?:LOCAL|Commercially)\b)"
)
_NOT_SPECIFIC_SPACING = (
    r"(?i)\bNot[ \t]{2,}sp[e\u00e9]cific\b"
    r"|\bNot[ \t]+sp[e\u00e9]cific[ \t]+[-\u2010-\u2015\u2212]"
    r"|\bNot[ \t]+sp[e\u00e9]cific[-\u2010-\u2015\u2212][ \t]+\w"
)
_DESICCANT_PATTERN = r"(?i)\bsilica[\s-]*gel\b|\bdes{1,2}ic{1,2}ant(?:\s+bags?)?\b"


def _address_check(index: int) -> Check:
    pattern, display = _ADDRESS_ELEMENTS[index]
    neighbour = index + 1 if index + 1 < len(_ADDRESS_ELEMENTS) else index - 1
    return Check(
        field="text",
        operator="regex_exists",
        expected=pattern,
        expected_display=display,
        suggestion_mode="fuzzy",
        missing_anchor=_ADDRESS_ELEMENTS[neighbour][0],
        missing_anchor_position="above" if index + 1 < len(_ADDRESS_ELEMENTS) else "below",
    )


# ---------------------------------------------------------------- Général

S1000D_MIGRATION_DM_DATES = rule(  # 5
    code="S1000D_MIGRATION_DM_DATES",
    name="Migration : dates de tous les DM mises à jour",
    description=(
        "Pour une migration, la date d'émission (issue date) de tous les data modules "
        "listés dans la LIST OF EFFECTIVE DATA MODULES doit être la date de révision "
        "du mapping, hors DM génériques (partagés, ils gardent leur propre date). "
        "S'applique quand le type de mise à jour du mapping est Migration."
    ),
    message="La date d'un DM de la LOEDM diffère de la date de révision.",
    kind="field_consistency",
    severity="error",
    target=_TARGET,
    checks=[_dm_status("loedm_dates_all")],
    only_if=_MIGRATION,
    failure_message="date d'un DM non mise à jour (migration).",
    translations={
        "en": {
            "description": (
                "For a migration, the issue date of every data module listed in the LIST OF "
                "EFFECTIVE DATA MODULES must be the revision date of the mapping, except generic "
                "DMs (shared, they keep their own date). Applies when the update type of the "
                "mapping is Migration."
            ),
            "message": "A DM date in the LOEDM differs from the revision date.",
        }
    },
)

S1000D_MCO_DM_DATES = rule(  # 6
    code="S1000D_MCO_DM_DATES",
    name="MCO : dates des DM modifiés mises à jour",
    description=(
        "Pour un MCO, la date d'émission des data modules modifiés (statut C, N, R ou S "
        "dans la LOEDM) doit être la date de révision du mapping."
    ),
    message="La date d'un DM modifié diffère de la date de révision.",
    kind="field_consistency",
    severity="error",
    target=_TARGET,
    checks=[_dm_status("loedm_dates_modified")],
    only_if=_MCO,
    failure_message="date d'un DM modifié non mise à jour (MCO).",
    translations={
        "en": {
            "description": (
                "For a maintenance update (MCO), the issue date of modified data modules "
                "(status C, N, R or S in the LOEDM) must be the revision date of the mapping."
            ),
            "message": "The date of a modified DM differs from the revision date.",
        }
    },
)

S1000D_MIGRATION_REVISION_ISSUE = rule(  # 7
    code="S1000D_MIGRATION_REVISION_ISSUE",
    name="Migration : numéro de révision et issue date modifiés",
    description=(
        "Pour une migration, le numéro de révision et l'issue date du bloc d'identification "
        "du document (première page) doivent être ceux du mapping."
    ),
    message="Le numéro de révision ou l'issue date ne correspond pas au mapping.",
    kind="field_consistency",
    severity="error",
    target=_TARGET,
    checks=[_front_matter("revision_identification")],
    only_if=_MIGRATION,
    failure_message="numéro de révision ou issue date non mis à jour (migration).",
    translations={
        "en": {
            "description": (
                "For a migration, the revision number and issue date of the document "
                "identification block (first page) must match the mapping."
            ),
            "message": "The revision number or issue date does not match the mapping.",
        }
    },
)

S1000D_MCO_REVISION_ROW = rule(  # 8
    code="S1000D_MCO_REVISION_ROW",
    name="MCO : ligne ajoutée avec le numéro de révision et l'issue date",
    description=(
        "Pour un MCO, le Record of revisions doit contenir une ligne avec le numéro de "
        "révision et l'issue date du mapping."
    ),
    message="Aucune ligne du Record of revisions pour la révision courante.",
    kind="field_required",
    severity="error",
    target=_TARGET,
    checks=[_front_matter("revision_record_row")],
    only_if=_MCO,
    failure_message="ligne de révision absente du Record of revisions (MCO).",
    translations={
        "en": {
            "description": (
                "For a maintenance update (MCO), the Record of revisions must contain a row "
                "with the revision number and issue date of the mapping."
            ),
            "message": "No Record of revisions row for the current revision.",
        }
    },
)

S1000D_CHANGED_DM_REVISION_BARS = rule(  # 9
    code="S1000D_CHANGED_DM_REVISION_BARS",
    name="DM « changed » : barres de révision et RFU présentes",
    description=(
        "Chaque data module au statut C (changed) dans la LOEDM doit porter des barres "
        "de révision et ses RFU (reasons for update)."
    ),
    message="Un DM au statut C n'a pas de barre de révision ou de RFU.",
    kind="field_consistency",
    severity="error",
    target=_TARGET,
    checks=[_dm_status("changed_dm_revision_bars")],
    failure_message="barre de révision ou RFU absent d'un DM au statut C.",
    translations={
        "en": {
            "description": (
                "Every data module with status C (changed) in the LOEDM must carry revision "
                "bars and its RFUs (reasons for update)."
            ),
            "message": "A DM with status C has no revision bar or RFU.",
        }
    },
)

S1000D_UNCHANGED_DM_NO_REVISION_BARS = rule(  # 10
    code="S1000D_UNCHANGED_DM_NO_REVISION_BARS",
    name="DM « revised » et « status » : aucune barre de révision",
    description=(
        "Les data modules aux statuts R (revised) et S (status) dans la LOEDM ne doivent "
        "contenir aucune barre de révision."
    ),
    message="Un DM au statut revised/status contient une barre de révision.",
    kind="field_consistency",
    severity="warning",
    target=_TARGET,
    checks=[_dm_status("unchanged_dm_no_revision_bars")],
    failure_message="barre de révision dans un DM revised/status.",
    translations={
        "en": {
            "description": (
                "Data modules with status R (revised) and S (status) in the LOEDM must not "
                "contain any revision bar."
            ),
            "message": "A revised/status DM contains a revision bar.",
        }
    },
)

S1000D_DATA_RESTRICTION_COPYRIGHT = rule(  # 11
    code="S1000D_DATA_RESTRICTION_COPYRIGHT",
    name="Data restriction : copyright THALES à jour",
    description=(
        "Le copyright « © AAAA-AAAA THALES AVS FRANCE SAS. This document and any data "
        "included are the property of THALES AVS FRANCE SAS. They cannot be reproduced, "
        "disclosed or used without the company's prior written approval » doit être présent. "
        "L'année de début est l'année de première issue et l'année de fin l'année de révision "
        "du mapping."
    ),
    message="Le copyright est absent ou une année est incorrecte.",
    kind="field_required",
    severity="error",
    target=_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=_COPYRIGHT_PATTERN,
            expected_display=_COPYRIGHT_DISPLAY,
            suggestion_mode="fuzzy",
        ),
        _front_matter("copyright_years"),
    ],
    failure_message="copyright de la data restriction non conforme.",
    translations={
        "en": {
            "description": (
                "The copyright \"\u00a9 YYYY-YYYY THALES AVS FRANCE SAS. This document and any "
                "data included are the property of THALES AVS FRANCE SAS. They cannot be "
                "reproduced, disclosed or used without the company's prior written approval\" "
                "must be present. The start year is the first issue year and the end year the "
                "revision year of the mapping."
            ),
            "message": "The copyright is missing or contains an incorrect year.",
        }
    },
)

S1000D_QA_FIRST_VERIFICATION = rule(  # 12
    code="S1000D_QA_FIRST_VERIFICATION",
    name="Quality assurance : first verification TABTOP",
    description=(
        "La first verification doit être TABTOP. Le PDF n'affiche pas la balise : il la rend par "
        "« The shop verification will be done at the first repair of the equipment » (ou "
        "« First verification : TABTOP »). Toute autre valeur (par exemple « Shop check which "
        "is done by performance ») est signalée."
    ),
    message="La first verification TABTOP est absente ou différente.",
    kind="field_required",
    severity="error",
    target=_TARGET,
    checks=[_content("first_verification")],
    failure_message="first verification TABTOP absente ou différente.",
    translations={
        "en": {
            "description": (
                "The first verification must be TABTOP. The PDF does not print the tag: it "
                "renders it as \"The shop verification will be done at the first repair of the "
                "equipment\" (or \"First verification: TABTOP\"). Any other value (for example "
                "\"Shop check which is done by performance\") is reported."
            ),
            "message": "The TABTOP first verification is missing or different.",
        }
    },
)

S1000D_THALES_ADDRESS = rule(  # 13
    code="S1000D_THALES_ADDRESS",
    name="Adresse THALES conforme",
    description=(
        "L'adresse THALES de référence doit être présente : 75-77 AV MARCEL DASSAULT, "
        "33700 MERIGNAC FRANCE, Tel: 05 24 44 77 40, www.thalesgroup.com."
    ),
    message="L'adresse THALES est absente ou incorrecte.",
    kind="field_required",
    severity="error",
    target=_TARGET,
    checks=[_address_check(index) for index in range(len(_ADDRESS_ELEMENTS))],
    failure_message="adresse THALES non conforme.",
    translations={
        "en": {
            "description": (
                "The reference THALES address must be present: 75-77 AV MARCEL DASSAULT, "
                "33700 MERIGNAC FRANCE, Tel: 05 24 44 77 40, www.thalesgroup.com."
            ),
            "message": "The THALES address is missing or incorrect.",
        }
    },
)

S1000D_SPM_LINK_AIRBUS = rule(  # 14
    code="S1000D_SPM_LINK_AIRBUS",
    name="Liens SPM (Airbus) conformes",
    description=(
        "Chaque renvoi « Refer to SPM » doit être suivi de « 20-02-00 - STANDARD PRACTICES "
        "MANUAL (SPM) »."
    ),
    message="Un renvoi vers le SPM n'est pas conforme à « Refer to SPM 20-02-00 - STANDARD PRACTICES MANUAL (SPM) ».",
    kind="regex_flag",
    severity="error",
    target=_TARGET,
    checks=[Check(field="text", operator="regex", expected=_SPM_LINK_PATTERN)],
    only_if=_AIRBUS,
    failure_message="renvoi SPM non conforme.",
    translations={
        "en": {
            "description": (
                "Every \"Refer to SPM\" reference must be followed by \"20-02-00 - STANDARD "
                "PRACTICES MANUAL (SPM)\"."
            ),
            "message": (
                "A SPM reference does not match \"Refer to SPM 20-02-00 - STANDARD PRACTICES "
                "MANUAL (SPM)\"."
            ),
        }
    },
)

S1000D_SOPM_LINK_BOEING = rule(  # 15
    code="S1000D_SOPM_LINK_BOEING",
    name="Liens SOPM (Boeing) conformes",
    description=(
        "Chaque renvoi « Refer to SOPM » doit être suivi de « 20-02-00 - STANDARD OVERHAUL "
        "PRACTICES MANUAL (SOPM) »."
    ),
    message=(
        "Un renvoi vers le SOPM n'est pas conforme à « Refer to SOPM 20-02-00 - STANDARD "
        "OVERHAUL PRACTICES MANUAL (SOPM) »."
    ),
    kind="regex_flag",
    severity="error",
    target=_TARGET,
    checks=[Check(field="text", operator="regex", expected=_SOPM_LINK_PATTERN)],
    only_if=_BOEING,
    failure_message="renvoi SOPM non conforme.",
    translations={
        "en": {
            "description": (
                "Every \"Refer to SOPM\" reference must be followed by \"20-02-00 - STANDARD "
                "OVERHAUL PRACTICES MANUAL (SOPM)\"."
            ),
            "message": (
                "A SOPM reference does not match \"Refer to SOPM 20-02-00 - STANDARD OVERHAUL "
                "PRACTICES MANUAL (SOPM)\"."
            ),
        }
    },
)

S1000D_MCO_LOEDM_STATUS = rule(  # 16
    code="S1000D_MCO_LOEDM_STATUS",
    name="MCO : statut des DM modifiés dans la LOEDM",
    description=(
        "Pour un MCO, tout data module modifié (issue date = date de révision) doit avoir un "
        "statut dans la LIST OF EFFECTIVE DATA MODULES (C pour un DM dont le contenu change)."
    ),
    message="Un DM modifié n'a pas de statut dans la LOEDM.",
    kind="field_consistency",
    severity="error",
    target=_TARGET,
    checks=[_dm_status("loedm_status_modified")],
    only_if=_MCO,
    failure_message="statut absent pour un DM modifié (MCO).",
    translations={
        "en": {
            "description": (
                "For a maintenance update (MCO), every modified data module (issue date = "
                "revision date) must have a status in the LIST OF EFFECTIVE DATA MODULES "
                "(C for a DM whose content changes)."
            ),
            "message": "A modified DM has no status in the LOEDM.",
        }
    },
)

S1000D_MIGRATION_LOEDM_STATUS = rule(  # 17
    code="S1000D_MIGRATION_LOEDM_STATUS",
    name="Migration : tous les DM au statut C hors DM génériques",
    description=(
        "Pour une migration, tous les data modules de la LIST OF EFFECTIVE DATA MODULES "
        "doivent avoir le statut C, hors DM génériques."
    ),
    message="Un DM n'a pas le statut C dans la LOEDM.",
    kind="field_consistency",
    severity="error",
    target=_TARGET,
    checks=[_dm_status("loedm_status_all")],
    only_if=_MIGRATION,
    failure_message="statut C absent pour un DM (migration).",
    translations={
        "en": {
            "description": (
                "For a migration, every data module of the LIST OF EFFECTIVE DATA MODULES must "
                "have status C, except generic DMs."
            ),
            "message": "A DM does not have status C in the LOEDM.",
        }
    },
)

# ----------------------------------------------------- Preliminary requirements

S1000D_SUPPORT_EQUIPMENT_LOCAL_MNF = rule(  # 18
    code="S1000D_SUPPORT_EQUIPMENT_LOCAL_MNF",
    name="Support equipment : code MNF LOCAL pour les outils « Not specific »",
    description=(
        "Dans les supports équipements, tout outil « Not specific-xxxxx » doit avoir le "
        "code MNF « LOCAL ». Dans le tableau publié, le code LOCAL s'imprime « Commercially "
        "available » dans la colonne MFR qui suit « Not specific »."
    ),
    message="Un outil « Not specific » n'a pas le code MNF LOCAL.",
    kind="regex_flag",
    severity="warning",
    target=_TARGET,
    checks=[Check(field="text", operator="regex", expected=_NOT_SPECIFIC_WITHOUT_LOCAL)],
    failure_message="code MNF LOCAL absent pour un outil Not specific.",
    translations={
        "en": {
            "description": (
                "In the support equipment, every \"Not specific-xxxxx\" tool must have the "
                "MNF code \"LOCAL\". In the published table, the LOCAL code is printed "
                "\"Commercially available\" in the MFR column that follows \"Not specific\"."
            ),
            "message": "A \"Not specific\" tool does not have the LOCAL MNF code.",
        }
    },
)

S1000D_TOOL_NAME_NO_SPACE = rule(  # 19
    code="S1000D_TOOL_NAME_NO_SPACE",
    name="Nom d'outil sans espace parasite",
    description=(
        "Le nom d'un outil « Not specific-xxxxx » ne doit contenir aucun espace parasite "
        "(espaces doubles, espace autour du tiret)."
    ),
    message="Le nom d'un outil « Not specific » contient un espace parasite.",
    kind="regex_flag",
    severity="warning",
    target=_TARGET,
    checks=[Check(field="text", operator="regex", expected=_NOT_SPECIFIC_SPACING)],
    failure_message="espace parasite dans un nom d'outil.",
    translations={
        "en": {
            "description": (
                "The name of a \"Not specific-xxxxx\" tool must not contain any stray space "
                "(double spaces, space around the hyphen)."
            ),
            "message": "A \"Not specific\" tool name contains a stray space.",
        }
    },
)

S1000D_TOOL_LINK_WORKS = rule(  # 20
    code="S1000D_TOOL_LINK_WORKS",
    name="Liens de la procédure vers les outils fonctionnels",
    description=(
        "Les liens de la procédure (outillage) doivent avoir une destination valide dans "
        "le PDF."
    ),
    message="Un lien de la procédure n'a pas de destination valide.",
    kind="field_consistency",
    severity="error",
    target=_TARGET,
    checks=[_content("broken_links_procedure")],
    failure_message="lien de la procédure sans destination valide.",
    translations={
        "en": {
            "description": "Links of the procedure (tooling) must have a valid destination in the PDF.",
            "message": "A procedure link has no valid destination.",
        }
    },
)

# --------------------------------------------------------------- Main procedure

S1000D_NUMBERS_IN_WORDS = rule(  # 21
    code="S1000D_NUMBERS_IN_WORDS",
    name="Chiffres de 0 à 9 en lettres, à partir de 10 en chiffres",
    description=(
        "Dans le texte courant, les nombres de 0 à 9 s'écrivent en lettres et ceux à partir "
        "de 10 en chiffres. Les valeurs avec unité, les références et les numérotations ne "
        "sont pas contrôlées."
    ),
    message="Un nombre n'est pas écrit selon la règle lettres (0-9) / chiffres (10 et plus).",
    kind="regex_flag",
    severity="warning",
    target=_TARGET,
    checks=[_content("numbers_in_words")],
    failure_message="nombre mal écrit (lettres 0-9, chiffres à partir de 10).",
    translations={
        "en": {
            "description": (
                "In running text, numbers from 0 to 9 are written in words and numbers from 10 "
                "onwards in digits. Values with units, references and numbering are not checked."
            ),
            "message": "A number does not follow the words (0-9) / digits (10 and more) rule.",
        }
    },
)

S1000D_PROCEDURE_LIST_STYLE = rule(  # 22
    code="S1000D_PROCEDURE_LIST_STYLE",
    name="Procédure : sous-étapes en (a), (b) sans tiret",
    description=(
        "Dans le paragraphe Main procedure, les sous-étapes utilisent les repères (a), (b)... "
        "et non un tiret."
    ),
    message="Un tiret est utilisé à la place d'un repère (a), (b) dans la procédure.",
    kind="step_pattern",
    severity="warning",
    target=_TARGET,
    checks=[_content("procedure_list_markers")],
    failure_message="tiret utilisé à la place d'un repère (a) dans la procédure.",
    translations={
        "en": {
            "description": (
                "In the Main procedure paragraph, sub-steps use the markers (a), (b)... and not "
                "a dash."
            ),
            "message": "A dash is used instead of an (a), (b) marker in the procedure.",
        }
    },
)

S1000D_JOB_SETUP_PRELIMINARY_CONDITIONS = rule(  # 23
    code="S1000D_JOB_SETUP_PRELIMINARY_CONDITIONS",
    name="Job set up : sous-paragraphe « Preliminary conditions »",
    description=(
        "Lorsque le Job set up comporte plusieurs paragraphes, il doit contenir un "
        "sous-paragraphe « Preliminary conditions »."
    ),
    message="Le Job set up a plusieurs paragraphes sans « Preliminary conditions ».",
    kind="section_required",
    severity="warning",
    target=_TARGET,
    checks=[_content("job_setup_preliminary_conditions")],
    failure_message="sous-paragraphe Preliminary conditions absent du Job set up.",
    translations={
        "en": {
            "description": (
                "When the Job set up has several paragraphs, it must contain a \"Preliminary "
                "conditions\" sub-paragraph."
            ),
            "message": "The Job set up has several paragraphs without \"Preliminary conditions\".",
        }
    },
)

S1000D_JOB_SETUP_TOOLING_TABLE = rule(  # 24
    code="S1000D_JOB_SETUP_TOOLING_TABLE",
    name="Job set up : tableau de complément d'information outillage",
    description=(
        "Le Job set up doit ajouter un tableau de complément d'information outillage lorsque "
        "les informations diffèrent du DM CIR. Le DM CIR n'étant pas dans le PDF, le contrôle "
        "signale à vérifier (inconclusif) lorsqu'aucun tableau n'est trouvé."
    ),
    message="Vérifier si un tableau de complément d'information outillage est nécessaire.",
    kind="section_required",
    severity="info",
    target=_TARGET,
    checks=[_content("job_setup_tooling_table")],
    failure_message="tableau de complément d'information outillage à vérifier.",
    translations={
        "en": {
            "description": (
                "The Job set up must add a tooling complement information table when the "
                "information differs from the CIR DM. The CIR DM is not in the PDF, so the "
                "check reports \"to verify\" (inconclusive) when no table is found."
            ),
            "message": "Check whether a tooling complement information table is required.",
        }
    },
)

# ------------------------------------------------------------------ DM SB record

S1000D_SB_RECORD_FORMAT = rule(  # 25
    code="S1000D_SB_RECORD_FORMAT",
    name="DM SB record conforme au modèle",
    description=(
        "Le DM Service bulletin record doit reprendre le texte du modèle (introduction, cinq "
        "colonnes, NOTE sur les SIL) et le tableau « SB (Number and revision, Title) / "
        "Equipment part number modification state / SB release date / Inserted number »."
    ),
    message="Le DM SB record ne reprend pas le texte ou le tableau du modèle.",
    kind="field_required",
    severity="error",
    target=_TARGET,
    checks=[_front_matter("sb_record_template")],
    failure_message="DM SB record non conforme au modèle.",
    translations={
        "en": {
            "description": (
                "The Service bulletin record DM must reuse the template text (introduction, five "
                "columns, SIL NOTE) and the table \"SB (Number and revision, Title) / Equipment "
                "part number modification state / SB release date / Inserted number\"."
            ),
            "message": "The SB record DM does not reuse the template text or table.",
        }
    },
)

S1000D_SB_SIL_ACRONYMS = rule(  # 26
    code="S1000D_SB_SIL_ACRONYMS",
    name="Acronymes SB et SIL dans la LIST OF ABBREVIATIONS",
    description="La LIST OF ABBREVIATIONS doit définir les acronymes SB et SIL.",
    message="L'acronyme SB ou SIL est absent de la LIST OF ABBREVIATIONS.",
    kind="field_required",
    severity="warning",
    target=_TARGET,
    checks=[_front_matter("abbreviation_acronyms")],
    failure_message="acronyme SB ou SIL absent de la liste des abréviations.",
    translations={
        "en": {
            "description": "The LIST OF ABBREVIATIONS must define the acronyms SB and SIL.",
            "message": "The SB or SIL acronym is missing from the LIST OF ABBREVIATIONS.",
        }
    },
)

# ------------------------------------------------------------ DM 00A-970A / tests

S1000D_SHOP_VERIFICATION = rule(  # 27
    code="S1000D_SHOP_VERIFICATION",
    name="DM 00A-970A : Shop verification présente",
    description="Le DM 00A-970A doit contenir la Shop verification.",
    message="La Shop verification est absente.",
    kind="section_required",
    severity="error",
    target=_TARGET,
    checks=[
        Check(
            field="text",
            operator="regex_exists",
            expected=_SHOP_VERIFICATION_PATTERN,
            expected_display="Shop Verification",
            suggestion_mode="fuzzy",
        )
    ],
    failure_message="Shop verification absente.",
    translations={
        "en": {
            "description": "The 00A-970A DM must contain the Shop verification.",
            "message": "The Shop verification is missing.",
        }
    },
)

S1000D_HUMIDITY_DM_REFERENCE = rule(  # 28
    code="S1000D_HUMIDITY_DM_REFERENCE",
    name="Function test : renvoi à jour vers le DM relative humidity",
    description=(
        "Chaque « Relative humidity » doit renvoyer au DM à jour : « Refer to Standard "
        "Practices Manual ATA No. 20-02-00, F9111CMON-A-20-02-00-00A-800A-A - Storage - "
        "General procedure ». Le manuel cité suit le constructeur du mapping : SPM pour Airbus, "
        "SOPM pour Boeing (texte Boeing déduit du texte Airbus de l'Excel, à confirmer)."
    ),
    message="Le renvoi vers le DM relative humidity est absent ou n'est pas à jour.",
    kind="field_required",
    severity="error",
    target=_TARGET,
    checks=[_content("humidity_reference")],
    failure_message="renvoi relative humidity absent ou non à jour.",
    translations={
        "en": {
            "description": (
                "Every \"Relative humidity\" must refer to the up-to-date DM: \"Refer to "
                "Standard Practices Manual ATA No. 20-02-00, F9111CMON-A-20-02-00-00A-800A-A - "
                "Storage - General procedure\". The manual follows the manufacturer of the "
                "mapping: SPM for Airbus, SOPM for Boeing (Boeing text derived from the Airbus "
                "text of the spreadsheet, to be confirmed)."
            ),
            "message": "The relative humidity DM reference is missing or out of date.",
        }
    },
)

S1000D_DETAILED_BREAKDOWN_TABLE = rule(  # 29
    code="S1000D_DETAILED_BREAKDOWN_TABLE",
    name="Tableau Detailed breakdown conforme au modèle",
    description=(
        "Si le tableau de composition (detailed breakdown) est présent, ses colonnes suivent "
        "le modèle : Nomenclature, Part Number, Amendment Status (A à F), Equipment "
        "Designator, ATA No."
    ),
    message="Le tableau Detailed breakdown ne suit pas le modèle de colonnes.",
    kind="field_required",
    severity="warning",
    target=_TARGET,
    checks=[_content("breakdown_table")],
    failure_message="tableau detailed breakdown non conforme au modèle.",
    translations={
        "en": {
            "description": (
                "If the composition (detailed breakdown) table is present, its columns follow "
                "the template: Nomenclature, Part Number, Amendment Status (A to F), Equipment "
                "Designator, ATA No."
            ),
            "message": "The Detailed breakdown table does not follow the column template.",
        }
    },
)

# ------------------------------------------------------------------------ STORAGE

S1000D_STORAGE_TEMPERATURE_NOTE = rule(  # 30
    code="S1000D_STORAGE_TEMPERATURE_NOTE",
    name="STORAGE : NOTE de renvoi au DM des conditions de température",
    description=(
        "La page STORAGE doit contenir la NOTE « During storage operations, make sure that the "
        "environmental conditions are as follows: - Temperature: Refer to SPM 20-02-00 - "
        "STANDARD PRACTICES MANUAL (SPM), Refer to F9111CMON-A-20-02-00-00A-812A-A - Storage "
        "and Transportation of Assemblies. ». D'autres conditions (pressure, relative humidity) "
        "peuvent la précéder ; les renvois étant imprimés après le texte, seule leur présence "
        "est contrôlée. Le manuel cité suit le constructeur du mapping : SPM pour Airbus, SOPM "
        "pour Boeing (texte Boeing déduit du texte Airbus de l'Excel, à confirmer)."
    ),
    message="La NOTE de renvoi au DM température du STORAGE est absente ou incorrecte.",
    kind="field_required",
    severity="error",
    target=_TARGET,
    checks=[_content("storage_temperature_note")],
    failure_message="NOTE STORAGE de renvoi température absente ou incorrecte.",
    translations={
        "en": {
            "description": (
                "The STORAGE page must contain the NOTE \"During storage operations, make sure "
                "that the environmental conditions are as follows: - Temperature: Refer to SPM "
                "20-02-00 - STANDARD PRACTICES MANUAL (SPM), Refer to "
                "F9111CMON-A-20-02-00-00A-812A-A - Storage and Transportation of Assemblies.\" "
                "Other conditions (pressure, relative humidity) may precede it; the references "
                "are printed after the text, so only their presence is checked. The manual "
                "follows the manufacturer of the mapping: SPM for Airbus, SOPM for Boeing "
                "(Boeing text derived from the Airbus text of the spreadsheet, to be confirmed)."
            ),
            "message": "The STORAGE temperature DM reference NOTE is missing or incorrect.",
        }
    },
)

S1000D_STORAGE_NO_OTHER_TEMPERATURE = rule(  # 31
    code="S1000D_STORAGE_NO_OTHER_TEMPERATURE",
    name="STORAGE : aucune autre mention de température",
    description=(
        "Hors du renvoi de la NOTE, la page STORAGE ne doit contenir aucune autre mention des "
        "conditions de température."
    ),
    message="Une mention de température subsiste dans le STORAGE.",
    kind="regex_flag",
    severity="error",
    target=_TARGET,
    checks=[_content("storage_other_temperature")],
    failure_message="autre mention de température dans le STORAGE.",
    translations={
        "en": {
            "description": (
                "Apart from the NOTE reference, the STORAGE page must not contain any other "
                "mention of temperature conditions."
            ),
            "message": "A temperature mention remains in the STORAGE.",
        }
    },
)

S1000D_NO_SILICA_GEL_DESICCANT = rule(  # 32
    code="S1000D_NO_SILICA_GEL_DESICCANT",
    name="Consommables Silica gel et dessicant bag supprimés",
    description="Les références au consommable Silica gel ou desiccant bag doivent être supprimées.",
    message="Référence à Silica gel ou desiccant bag à supprimer.",
    kind="regex_flag",
    severity="error",
    target=_TARGET,
    checks=[Check(field="text", operator="regex", expected=_DESICCANT_PATTERN, replacement="")],
    failure_message="référence Silica gel / desiccant bag à supprimer.",
    translations={
        "en": {
            "description": "References to the Silica gel or desiccant bag consumable must be removed.",
            "message": "Silica gel or desiccant bag reference to remove.",
        }
    },
)

# ------------------------------------------------------- Disassembly / Assembly

S1000D_LOCTITE_SCREW_SIZE = rule(  # 33
    code="S1000D_LOCTITE_SCREW_SIZE",
    name="Loctite 221 pour vis < M5, Loctite 222 pour vis > M5",
    description=(
        "Dans les DM de désassemblage (500A) et d'assemblage (700A), Loctite 221 est réservé "
        "aux vis inférieures à M5 et Loctite 222 aux vis supérieures à M5."
    ),
    message="La référence Loctite ne correspond pas au diamètre de vis.",
    kind="field_consistency",
    severity="warning",
    target=_TARGET,
    checks=[_content("loctite_grade")],
    failure_message="référence Loctite incohérente avec le diamètre de vis.",
    translations={
        "en": {
            "description": (
                "In the disassembly (500A) and assembly (700A) DMs, Loctite 221 is reserved for "
                "screws smaller than M5 and Loctite 222 for screws larger than M5."
            ),
            "message": "The Loctite reference does not match the screw size.",
        }
    },
)

# ------------------------------------------------------------------------- IPL

S1000D_IPL_ILLUSTRATION_REVISION_BAR = rule(  # 34
    code="S1000D_IPL_ILLUSTRATION_REVISION_BAR",
    name="IPL : barre de révision sur l'illustration mise à jour",
    description=(
        "Si l'illustration de l'IPL est mise à jour, elle doit porter une barre de révision. "
        "Les marques d'une illustration pouvant être intégrées à l'image, le contrôle signale "
        "à vérifier (inconclusif) lorsqu'aucune barre n'est détectée."
    ),
    message="Vérifier la barre de révision de l'illustration mise à jour de l'IPL.",
    kind="field_consistency",
    severity="warning",
    target=_TARGET,
    checks=[_dm_status("ipl_illustration_revision_bars")],
    failure_message="barre de révision de l'illustration IPL à vérifier.",
    translations={
        "en": {
            "description": (
                "If the IPL illustration is updated, it must carry a revision bar. Illustration "
                "marks can be embedded in the image, so the check reports \"to verify\" "
                "(inconclusive) when no bar is detected."
            ),
            "message": "Check the revision bar of the updated IPL illustration.",
        }
    },
)

S1000D_IPL_REVISION_BARS = rule(  # 35
    code="S1000D_IPL_REVISION_BARS",
    name="IPL mise à jour : barres de révision présentes",
    description="Si le DM de l'IPL est mis à jour (statut C), ses pages doivent porter des barres de révision.",
    message="L'IPL mise à jour n'a pas de barre de révision.",
    kind="field_consistency",
    severity="error",
    target=_TARGET,
    checks=[_dm_status("ipl_revision_bars")],
    failure_message="barre de révision absente de l'IPL mise à jour.",
    translations={
        "en": {
            "description": (
                "If the IPL DM is updated (status C), its pages must carry revision bars."
            ),
            "message": "The updated IPL has no revision bar.",
        }
    },
)

S1000D_IPL_LINKS = rule(  # 36
    code="S1000D_IPL_LINKS",
    name="Liens de l'IPL fonctionnels",
    description="Les liens présents dans l'IPL doivent avoir une destination valide dans le PDF.",
    message="Un lien de l'IPL n'a pas de destination valide.",
    kind="field_consistency",
    severity="error",
    target=_TARGET,
    checks=[_content("broken_links_ipl")],
    failure_message="lien de l'IPL sans destination valide.",
    translations={
        "en": {
            "description": "Links in the IPL must have a valid destination in the PDF.",
            "message": "An IPL link has no valid destination.",
        }
    },
)

RULE_DEFINITIONS = (
    S1000D_MIGRATION_DM_DATES,
    S1000D_MCO_DM_DATES,
    S1000D_MIGRATION_REVISION_ISSUE,
    S1000D_MCO_REVISION_ROW,
    S1000D_CHANGED_DM_REVISION_BARS,
    S1000D_UNCHANGED_DM_NO_REVISION_BARS,
    S1000D_DATA_RESTRICTION_COPYRIGHT,
    S1000D_QA_FIRST_VERIFICATION,
    S1000D_THALES_ADDRESS,
    S1000D_SPM_LINK_AIRBUS,
    S1000D_SOPM_LINK_BOEING,
    S1000D_MCO_LOEDM_STATUS,
    S1000D_MIGRATION_LOEDM_STATUS,
    S1000D_SUPPORT_EQUIPMENT_LOCAL_MNF,
    S1000D_TOOL_NAME_NO_SPACE,
    S1000D_TOOL_LINK_WORKS,
    S1000D_NUMBERS_IN_WORDS,
    S1000D_PROCEDURE_LIST_STYLE,
    S1000D_JOB_SETUP_PRELIMINARY_CONDITIONS,
    S1000D_JOB_SETUP_TOOLING_TABLE,
    S1000D_SB_RECORD_FORMAT,
    S1000D_SB_SIL_ACRONYMS,
    S1000D_SHOP_VERIFICATION,
    S1000D_HUMIDITY_DM_REFERENCE,
    S1000D_DETAILED_BREAKDOWN_TABLE,
    S1000D_STORAGE_TEMPERATURE_NOTE,
    S1000D_STORAGE_NO_OTHER_TEMPERATURE,
    S1000D_NO_SILICA_GEL_DESICCANT,
    S1000D_LOCTITE_SCREW_SIZE,
    S1000D_IPL_ILLUSTRATION_REVISION_BAR,
    S1000D_IPL_REVISION_BARS,
    S1000D_IPL_LINKS,
    S1000D_HIGHLIGHTS_RFU_STATUS,
)

RULE_METADATA = {definition.code: definition.metadata for definition in RULE_DEFINITIONS}
CATALOG = {_CATALOG_VERSION: [definition.compiled_rule for definition in RULE_DEFINITIONS]}
STANDARD_SPEC: dict[str, object] = {
    "code": _STANDARD_CODE,
    "label": "THALES - Regles S1000D",
    "description": "Controles documentaires THALES pour les manuels au format S1000D.",
    "versions": CATALOG,
    "metadata": RULE_METADATA,
}
