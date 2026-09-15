"""THALES-specific compiled rules.

Add rules to ``_RULES_V1`` and restart the backend. The catalog is synchronized
into the local database at startup.
"""

from __future__ import annotations

import re
from typing import Literal

from app.core.compiled_rules import Check, CompiledRule, Condition, FieldRef, RuleTarget
from app.core.logging import get_logger
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


STANDARD_CODE = "THALES-CUSTOM"
STANDARD_LABEL = "THALES - Regles utilisateur"
STANDARD_DESCRIPTION = (
    "Regles locales editables pour tester des controles sur les documents."
)

_logger = get_logger(__name__)

_TARGET = RuleTarget(page="all", region="full_page")
_FOOTER_TARGET = RuleTarget(page="all", region="footer")
_TP1_REVISION_TARGET = RuleTarget(page="all", region="footer", page_type="TP1")
# full_page (et non footer) : sur ce standard, le bloc adresse THALES est
# positionne hors du bandeau bas-de-page a 25% calcule par `_scope_targets`
# (verifie en prod : le scope "footer" ne recupere qu'une partie du texte
# de la page, l'adresse en est exclue). On reste donc sur le texte brut de
# la page entiere, filtre uniquement par `page_type`.
_TP1_ADDRESS_TARGET = RuleTarget(page="all", region="full_page", page_type="TP1")
_ORIGIN = f"{STANDARD_CODE}:v1"
TP1_PAGE_TYPE = "TP1"
HIGHLIGHTS_PAGE_TYPE = "HIGHLIGHTS"
_HIGHLIGHTS_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_type=HIGHLIGHTS_PAGE_TYPE,
)
_HEADER_TARGET = RuleTarget(
    page="all",
    region="header",
    excluded_page_types=[TP1_PAGE_TYPE],
)
_HIGHLIGHTS_PNR_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_type=HIGHLIGHTS_PAGE_TYPE,
)
_TP1_PNR_TARGET = RuleTarget(
    page="all",
    region="body",
    page_type=TP1_PAGE_TYPE,
)
_FOOTER_BAND_MIN_HEIGHT = 80.0
_FOOTER_LINE_TOLERANCE = 3.0
_CMM_NUMBER_PATTERN = r"\d{2}-\d{2}-\d{2}"
_DECIMAL_COMMA_PATTERN = r"(?<!\d)(\d+),(\d+)(?!\d)"
_DEGREE_C_PATTERN = r"(?i)°\s*C\b"
_DEGREE_F_PATTERN = r"(?i)°\s*F\b"
_TEMPERATURE_WITHOUT_FAHRENHEIT_PATTERN = (
    r"(?i)(?<!\w)(?:temperature\s*:\s*)?"
    r"[+-]?\d+(?:[.,]\d+)?"
    r"(?:\s+to\s+[+-]?\d+(?:[.,]\d+)?)?\s+deg\.\s*C\b"
    r"(?!\s*\(\s*[+-]?\d+(?:[.,]\d+)?"
    r"(?:\s+to\s+[+-]?\d+(?:[.,]\d+)?)?\s+deg\.\s*F\s*\))"
)
_EXPECTED_TP1_REVISION_NUMBER_PATTERN = (
    r"(?i)(?<!\w)Revision\s+No\.?\s*{{meta_revision_number}}(?!\w)"
    r"(?=[\s\S]*\bFirst\s+Issue\b)"
)
_EXPECTED_TP1_FIRST_ISSUE_PATTERN = (
    r"(?i)(?<!\w)First\s+issue\s*:\s*{{meta_first_issue_date}}(?!\w)"
)
_EXPECTED_HIGHLIGHTS_REVISION_PATTERN = r"(?i)(?<!\w)REVISION\s+No\.?\s*{{meta_revision_number}}\s+DATED\s+{{meta_revision_date}}(?!\w)"
_EXPECTED_HIGHLIGHTS_PNR_PATTERN = r"(?<!\w){{meta_pnr_number}}(?!\w)"
_UNEXPECTED_PNR_PATTERN = (
    r"(?i)(?<!\w)(?!{{meta_pnr_number}}(?!\w))"
    r"\d+-\d{3}-[A-Z]{2}(?!\w)"
)
_UNEXPECTED_HIGHLIGHTS_PNR_PATTERN = (
    r"(?i)(?<=PNR: )(?!{{meta_pnr_number}}(?!\w))"
    r"\d+-\d{3}-[A-Z]{2}(?!\w)"
)
_EXPECTED_CMM_PATTERN = r"(?<!\w){{meta_cmm_number}}(?!\w)"
_EXPECTED_REVISION_DATE_PATTERN = r"(?<!\w){{meta_revision_date}}(?!\w)"
_COPYRIGHT_START_YEAR = "1966"
_COPYRIGHT_PATTERN = (
    r"\u00a9\s*\d{4}\s*-\s*\d{4}\s+"
    r"THALES\s+AVS\s+FRANCE\s+SAS\.\s+"
    r"This\s+document\s+and\s+any\s+data\s+included\s+are\s+the\s+property\s+of\s+"
    r"THALES\s+AVS\s+FRANCE\s+SAS\.\s+"
    r"They\s+cannot\s+be\s+reproduced,\s+disclosed\s+or\s+used\s+"
    r"without\s+the\s+company's\s+prior\s+written\s+approval\.?"
)
# One check per line keeps the reported missing element precise instead of
# returning one opaque failure for the whole address block.
_THALES_TP1_ADDRESS_ELEMENTS: tuple[tuple[str, str], ...] = (
    (r"\(F9111\)", "(F9111)"),
    (r"75-77\s+Avenue\s+Marcel\s+Dassault", "75-77 Avenue Marcel Dassault"),
    (r"33700\s+M\u00e9rignac\s+-\s+France", "33700 Mérignac - France"),
    (r"Tel\s*:\s*\+33\s+\(0\)5\s+24\s+44\s+77\s+40", "Tel : +33 (0)5 24 44 77 40"),
    (r"www\.thalesgroup\.com", "www.thalesgroup.com"),
)


def _normalized_line(value: str) -> str:
    return " ".join(value.split()).strip()


def _footer_lines(page: ParsedPage) -> list[str]:
    if not page.spans:
        return []
    min_y = min(span.bbox[1] for span in page.spans)
    max_y = max(span.bbox[3] for span in page.spans)
    footer_top = max_y - max((max_y - min_y) * 0.25, _FOOTER_BAND_MIN_HEIGHT)
    footer_spans = [span for span in page.spans if span.bbox[3] >= footer_top]
    groups: list[tuple[float, list[str]]] = []
    for span in sorted(footer_spans, key=lambda item: (item.bbox[1], item.bbox[0])):
        center_y = (span.bbox[1] + span.bbox[3]) / 2
        if groups and abs(center_y - groups[-1][0]) <= _FOOTER_LINE_TOLERANCE:
            groups[-1][1].append(span.text)
        else:
            groups.append((center_y, [span.text]))
    return [_normalized_line(" ".join(parts)) for _center_y, parts in groups]


def identify_page_type(
    parsed: ParsedPdf,
    page_name: str,
    revision_date: str | None,
    cmm_number: str | None = None,
) -> dict[str, str | None]:
    """Mark pages whose footer carries the anchors and the requested name.

    Originally required the TP1 marker on the footer line immediately below
    the anchor line, but real footers lay the CMM number, "First issue:",
    TP1 marker and revision date out as a multi-column block: the naive
    y-position line grouping in `_footer_lines` interleaves those short
    labels with the (wider, multi-line) copyright paragraph next to them,
    so the TP1 marker rarely ends up on the line right after the anchor.
    Co-occurrence anywhere in the footer band is a weaker but much more
    reliable signal for this layout.
    """
    expected_anchors = [
        _normalized_line(cmm_number or "").casefold(),
        _normalized_line(revision_date or "").casefold(),
    ]
    page_marker = r"\s*".join(re.escape(character) for character in page_name)
    page_marker_pattern = re.compile(rf"\b{page_marker}\b", re.IGNORECASE)
    expected_anchors = [anchor for anchor in expected_anchors if anchor]
    if not expected_anchors:
        _logger.warning(
            "tp1_detection_skipped_no_anchor",
            reason="meta_cmm_number et meta_revision_date absents du contexte document",
        )
    page_types: dict[str, str | None] = {}
    for page in parsed.pages:
        lines: list[str] = []
        if expected_anchors:
            lines = _footer_lines(page)
            footer_text = " ".join(lines).casefold()
            has_anchor = any(anchor in footer_text for anchor in expected_anchors)
            has_marker = bool(page_marker_pattern.search(footer_text))
            if has_anchor and has_marker:
                page.page_type = page_name
            elif page.page_type == page_name:
                page.page_type = None
        elif page.page_type == page_name:
            page.page_type = None
        if expected_anchors and page.page_type != page_name:
            # Aide au diagnostic : si zero page n'est jamais classee TP1,
            # compare `footer_lines` a la mise en page reelle du pied de
            # page (anchor et/ou marqueur absents du bandeau detecte).
            _logger.debug(
                "tp1_detection_no_match",
                page=page.page,
                expected_anchors=expected_anchors,
                footer_lines=lines,
            )
        page_types[str(page.page)] = page.page_type
    return page_types


def identify_tp1_pages(
    parsed: ParsedPdf,
    revision_date: str | None,
    cmm_number: str | None = None,
) -> dict[str, str | None]:
    """Backward-compatible wrapper for TP1 page classification."""
    return identify_page_type(parsed, TP1_PAGE_TYPE, revision_date, cmm_number)


def classify_pages(parsed: ParsedPdf, document: object) -> None:
    """`PAGE_CLASSIFIERS` entry point (see `app.checks.standards`): reads the
    anchors off `document` itself so the generic pipeline never has to know
    what this standard needs to classify a page."""
    identify_tp1_pages(
        parsed,
        getattr(document, "meta_revision_date", None),
        getattr(document, "meta_cmm_number", None),
    )
    identify_page_type(
        parsed,
        HIGHLIGHTS_PAGE_TYPE,
        getattr(document, "meta_revision_date", None),
        getattr(document, "meta_cmm_number", None),
    )


def _rule(
    code: str,
    topic: str,
    *,
    pattern: str | None = None,
    checks: list[Check] | None = None,
    target: RuleTarget = _TARGET,
    operator: Literal["regex", "regex_exists"] = "regex",
    severity: Literal["info", "warning", "error"] = "warning",
    failure_message: str | None = None,
    expected_display: str | None = None,
    missing_anchor: str | None = None,
    missing_anchor_position: Literal["above", "below"] = "above",
    replacement: str | None = None,
    only_if: Condition | None = None,
) -> CompiledRule:
    if pattern is not None and checks is not None:
        raise ValueError("_rule accepte soit pattern, soit checks, pas les deux")
    if checks is None:
        if pattern is None:
            raise ValueError("_rule exige pattern ou checks")
        checks = [
            Check(
                field="text",
                operator=operator,
                expected=pattern,
                expected_display=expected_display,
                missing_anchor=missing_anchor,
                missing_anchor_position=missing_anchor_position,
                replacement=replacement,
            )
        ]
    return CompiledRule(
        id=code,
        topic=topic,
        failure_message=failure_message,
        severity=severity,
        execution="deterministic",
        target=target,
        checks=checks,
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:{code}",
        only_if=only_if,
    )


def _required_text_check(
    pattern: str,
    *,
    display: str | None = None,
    suggestion_mode: Literal["fuzzy", "single", "all"] = "fuzzy",
    anchor: str | None = None,
    anchor_position: Literal["above", "below"] = "above",
) -> Check:
    return Check(
        field="text",
        operator="regex_exists",
        expected=pattern,
        require_all=True,
        expected_display=display,
        suggestion_mode=suggestion_mode,
        missing_anchor=anchor,
        missing_anchor_position=anchor_position,
    )


_RULES_V1 = [
    _rule(
        "CUSTOM_CMM_NUMBER",
        "Numero CMM conforme au contexte du document",
        failure_message="Numero CMM non conforme",
        target=_FOOTER_TARGET,
        severity="error",
        checks=[
            _required_text_check(
                _EXPECTED_CMM_PATTERN,
                display="{{meta_cmm_number}}",
                anchor=r"(?i)\bFirst\s+Issue\b",
            ),
        ],
    ),
    _rule(
        "CUSTOM_TITLE_PAGE_COPYRIGHT",
        "Copyright du footer conforme a l'annee de revision",
        failure_message="Copyright du footer non conforme",
        target=_FOOTER_TARGET,
        severity="error",
        checks=[
            Check(
                field="text",
                operator="regex_exists",
                expected=_COPYRIGHT_PATTERN,
            ),
            Check(
                field="copyright_start_year",
                operator="normalized_equals",
                expected=_COPYRIGHT_START_YEAR,
                normalization=["trim"],
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
    ),
    _rule(
        "CUSTOM_REVISION_DATE",
        "Date de revision du footer conforme au mapping",
        failure_message="Date de revision du footer non conforme",
        target=_FOOTER_TARGET,
        severity="error",
        checks=[
            _required_text_check(
                _EXPECTED_REVISION_DATE_PATTERN,
                display="{{meta_revision_date}}",
                anchor=r"(?i)\bFirst\s+Issue\b",
            ),
        ],
    ),
    _rule(
        "CUSTOM_TP1_REVISION_NUMBER",
        "Numero de revision du footer TP1 conforme au mapping",
        failure_message="numéro de revision non conforme.",
        target=_TP1_REVISION_TARGET,
        severity="error",
        checks=[
            _required_text_check(
                _EXPECTED_TP1_REVISION_NUMBER_PATTERN,
                display="Revision No. {{meta_revision_number}}",
                anchor=r"(?i)\bFirst\s+Issue\b",
            ),
        ],
    ),
    _rule(
        "CUSTOM_TP1_FIRST_ISSUE_DATE",
        "Date de premiere issue du footer TP1 conforme au mapping",
        failure_message="date de premiere issue non conforme.",
        target=_TP1_REVISION_TARGET,
        severity="error",
        checks=[
            _required_text_check(
                _EXPECTED_TP1_FIRST_ISSUE_PATTERN,
                display="First issue: {{meta_first_issue_date}}",
                anchor=r"(?i)Revision\s+No\.?\s*\d{2}",
                anchor_position="below",
            ),
        ],
    ),
    _rule(
        "CUSTOM_HIGHLIGHTS_REVISION_HEADER",
        "En-tete de revision present au-dessus du tableau Highlights",
        failure_message="En-tete de revision Highlights non conforme.",
        target=_HIGHLIGHTS_TARGET,
        severity="error",
        checks=[
            _required_text_check(
                _EXPECTED_HIGHLIGHTS_REVISION_PATTERN,
                display="REVISION No. {{meta_revision_number}} DATED {{meta_revision_date}}",
                suggestion_mode="single",
                anchor=r"(?i)\bHighlights\b",
                anchor_position="above",
            ),
        ],
    ),
    _rule(
        "CUSTOM_HIGHLIGHTS_PNR_HEADER",
        "Numero PNR present et conforme dans l'en-tete des pages",
        failure_message="Numero PNR de l'en-tete non conforme.",
        target=_HEADER_TARGET,
        severity="error",
        only_if=Condition(field="meta_pnr_number", state="present"),
        checks=[
            _required_text_check(
                _EXPECTED_HIGHLIGHTS_PNR_PATTERN,
                display="{{meta_pnr_number}}",
                suggestion_mode="all",
            ),
        ],
    ),
    _rule(
        "CUSTOM_PNR_PAGE_VALUE",
        "Numero PNR present dans la page conforme au mapping",
        failure_message="Numero PNR present dans la page non conforme.",
        target=_HIGHLIGHTS_PNR_TARGET,
        severity="error",
        only_if=Condition(field="meta_pnr_number", state="present"),
        pattern=_UNEXPECTED_HIGHLIGHTS_PNR_PATTERN,
        replacement="{{meta_pnr_number}}",
    ),
    _rule(
        "CUSTOM_TP1_PNR_PAGE_VALUE",
        "Numero PNR present dans la page TP1 conforme au mapping",
        failure_message="Numero PNR present dans la page TP1 non conforme.",
        target=_TP1_PNR_TARGET,
        severity="error",
        only_if=Condition(field="meta_pnr_number", state="present"),
        pattern=_UNEXPECTED_PNR_PATTERN,
        replacement="{{meta_pnr_number}}",
    ),
    _rule(
        "CUSTOM_TP1_THALES_ADDRESS",
        "Adresse THALES exacte sur les pages TP1",
        failure_message="adresse THALES non conforme.",
        target=_TP1_ADDRESS_TARGET,
        severity="error",
        checks=[
            _required_text_check(
                pattern,
                display=display,
                anchor=(
                    _THALES_TP1_ADDRESS_ELEMENTS[index + 1][0]
                    if index + 1 < len(_THALES_TP1_ADDRESS_ELEMENTS)
                    else _THALES_TP1_ADDRESS_ELEMENTS[index - 1][0]
                ),
                anchor_position=(
                    "above" if index + 1 < len(_THALES_TP1_ADDRESS_ELEMENTS) else "below"
                ),
            )
            for index, (pattern, display) in enumerate(_THALES_TP1_ADDRESS_ELEMENTS)
        ],
    ),
    _rule(
        "CUSTOM_DECIMAL_COMMA",
        "Valeurs decimales doivent etre separees par un point",
        pattern=_DECIMAL_COMMA_PATTERN,
        severity="error",
        replacement=r"\1.\2",
    ),
    _rule(
        "CUSTOM_TEMPERATURE_FAHRENHEIT",
        "Temperature en deg. C accompagnee de sa conversion en deg. F",
        failure_message="conversion Fahrenheit absente pour la temperature.",
        pattern=_TEMPERATURE_WITHOUT_FAHRENHEIT_PATTERN,
        severity="error",
        replacement="{{temperature_fahrenheit}}",
    ),
    _rule(
        "CUSTOM_NO_DEGREE_C_SYMBOL",
        "Unite de temperature C ecrite au format deg. C",
        failure_message="unite °C interdite, utiliser deg. C.",
        pattern=_DEGREE_C_PATTERN,
        severity="error",
        replacement="deg. C",
    ),
    _rule(
        "CUSTOM_NO_DEGREE_F_SYMBOL",
        "Unite de temperature F ecrite au format deg. F",
        failure_message="unite °F interdite, utiliser deg. F.",
        pattern=_DEGREE_F_PATTERN,
        severity="error",
        replacement="deg. F",
    ),
]


def _default_metadata(rule: CompiledRule) -> dict[str, object]:
    operator = rule.checks[0].operator if rule.checks else "regex"
    return {
        "description": rule.topic,
        "kind": "field_required" if operator == "regex_exists" else "regex_flag",
        "severity": rule.severity,
        "message": rule.topic,
    }


RULE_METADATA = {rule.id: _default_metadata(rule) for rule in _RULES_V1}
RULE_METADATA["CUSTOM_CMM_NUMBER"] = {
    "description": (
        "Le numero present dans le document doit correspondre a la valeur "
        "meta_cmm_number saisie dans le contexte du document."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Le numero CMM ne correspond pas au contexte du document.",
}
RULE_METADATA["CUSTOM_TITLE_PAGE_COPYRIGHT"] = {
    "description": (
        "Le footer du document doit contenir le copyright THALES avec "
        "l'annee de debut 1966 et l'annee de revision du document."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Le copyright du footer est absent ou une annee est incorrecte.",
}
RULE_METADATA["CUSTOM_REVISION_DATE"] = {
    "description": (
        "La date de revision presente dans le footer doit correspondre a la "
        "date de revision saisie dans le mapping du document."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "La date de revision du footer ne correspond pas au mapping.",
}
RULE_METADATA["CUSTOM_TP1_THALES_ADDRESS"] = {
    "description": (
        "Chaque page identifiee TP1 doit contenir exactement l'adresse THALES "
        "de reference."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "L'adresse THALES de la page TP1 est absente ou incorrecte.",
}
RULE_METADATA["CUSTOM_TP1_REVISION_NUMBER"] = {
    "description": (
        "Chaque page TP1 doit contenir dans son footer 'Revision No. 0X' "
        "au-dessus de 'First Issue', avec 0X egal au numero de revision "
        "saisi dans le mapping (sans le prefixe 'Rev.')."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": (
        "Le numero de revision du footer TP1 est absent ou ne correspond "
        "pas au mapping."
    ),
}
RULE_METADATA["CUSTOM_TP1_FIRST_ISSUE_DATE"] = {
    "description": (
        "Chaque page TP1 doit contenir dans son footer 'First Issue: date' "
        "avec une date egale a la date de premiere issue saisie dans le mapping."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": (
        "La date de premiere issue du footer TP1 est absente ou ne correspond "
        "pas au mapping."
    ),
}
RULE_METADATA["CUSTOM_HIGHLIGHTS_REVISION_HEADER"] = {
    "description": (
        "La page dont le nom contient Highlights doit afficher au-dessus du "
        "tableau l'en-tete REVISION No. avec le numero et la date du mapping."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": (
        "L'en-tete de revision Highlights est absent, incorrect ou place "
        "apres le tableau."
    ),
}
RULE_METADATA["CUSTOM_HIGHLIGHTS_PNR_HEADER"] = {
    "description": (
        "L'en-tete de chaque page doit contenir le numero PNR correspondant "
        "au mapping du document."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Le numero PNR de l'en-tete est absent ou incorrect.",
}
RULE_METADATA["CUSTOM_PNR_PAGE_VALUE"] = {
    "description": (
        "Le numero apres 'PNR:' sur la page Highlights doit correspondre au "
        "mapping du document."
    ),
    "kind": "regex_flag",
    "severity": "error",
    "message": "Le numero PNR de la page Highlights ne correspond pas au mapping.",
}
RULE_METADATA["CUSTOM_TP1_PNR_PAGE_VALUE"] = {
    "description": (
        "Tout numero PNR explicitement present dans le corps d'une page TP1 "
        "doit correspondre au mapping du document."
    ),
    "kind": "regex_flag",
    "severity": "error",
    "message": "Le numero PNR de la page TP1 ne correspond pas au mapping.",
}
RULE_METADATA["CUSTOM_DECIMAL_COMMA"] = {
    "description": (
        "Les valeurs numeriques decimales des pages modifiees doivent utiliser "
        "un point comme separateur decimal, et non une virgule."
    ),
    "kind": "regex_flag",
    "severity": "error",
    "message": "Une valeur decimale utilise une virgule au lieu d'un point.",
}
RULE_METADATA["CUSTOM_TEMPERATURE_FAHRENHEIT"] = {
    "description": (
        "Toute temperature exprimee en deg. C doit etre suivie de sa "
        "conversion numerique en deg. F entre parentheses."
    ),
    "kind": "regex_flag",
    "severity": "error",
    "message": "La temperature en deg. C doit etre suivie de sa conversion en deg. F.",
}
RULE_METADATA["CUSTOM_NO_DEGREE_C_SYMBOL"] = {
    "description": "Le symbole °C doit etre ecrit sous la forme deg. C.",
    "kind": "regex_flag",
    "severity": "error",
    "message": "Le symbole °C est interdit : utiliser deg. C.",
}
RULE_METADATA["CUSTOM_NO_DEGREE_F_SYMBOL"] = {
    "description": "Le symbole °F doit etre ecrit sous la forme deg. F.",
    "kind": "regex_flag",
    "severity": "error",
    "message": "Le symbole °F est interdit : utiliser deg. F.",
}


CATALOG: dict[str, list[CompiledRule]] = {"v1": _RULES_V1}


STANDARD_SPEC: dict[str, object] = {
    "code": STANDARD_CODE,
    "label": STANDARD_LABEL,
    "description": STANDARD_DESCRIPTION,
    "versions": CATALOG,
    "metadata": RULE_METADATA,
}