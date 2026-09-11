"""Local rules maintained for Doc Reviewer experiments.

Add or remove ``_regex_rule(...)`` entries in ``_RULES_V1`` and restart the
backend. The catalog is synchronized into the local database at startup.
"""

from __future__ import annotations

import re
from typing import Literal

from app.core.compiled_rules import Check, CompiledRule, FieldRef, RuleTarget
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
# full_page (et non footer) : sur ce standard, le bloc adresse THALES est
# positionne hors du bandeau bas-de-page a 25% calcule par `_scope_targets`
# (verifie en prod : le scope "footer" ne recupere qu'une partie du texte
# de la page, l'adresse en est exclue). On reste donc sur le texte brut de
# la page entiere, filtre uniquement par `page_type`.
_TP1_ADDRESS_TARGET = RuleTarget(page="all", region="full_page", page_type="TP1")
_ORIGIN = f"{STANDARD_CODE}:v1"
TP1_PAGE_TYPE = "TP1"
_TP1_MARKER_PATTERN = re.compile(r"\bTP\s*1\b", re.IGNORECASE)
_FOOTER_BAND_MIN_HEIGHT = 80.0
_FOOTER_LINE_TOLERANCE = 3.0
_CMM_NUMBER_PATTERN = r"\d{2}-\d{2}-\d{2}"
_DECIMAL_COMMA_PATTERN = r"(?<!\d)(\d+),(\d+)(?!\d)"
_EXPECTED_CMM_PATTERN = r"(?<!\w){{meta_cmm_number}}(?!\w)"
_REVISION_DATE_PATTERN = (
    r"(?:"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|(?i:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
    r"\s+\d{1,2}/\d{2,4}"
    r")"
)
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
_THALES_TP1_ADDRESS_PATTERN = (
    r"\(F9111\)\s+"
    r"75-77\s+Avenue\s+Marcel\s+Dassault\s+"
    r"33700\s+M\u00e9rignac\s+-\s+France\s+"
    r"Tel\s*:\s*\+33\s+\(0\)5\s+24\s+44\s+77\s+40\s+"
    r"www\.thalesgroup\.com"
)  # reference : les elements ci-dessous, mis bout a bout dans l'ordre attendu
# Un element par ligne (au lieu d'un seul bloc a tout-ou-rien) : un FAIL
# pointe alors sur l'element precis manquant/incorrect (ex: le code CAGE
# absent) au lieu de "l'adresse entiere ne correspond pas".
_THALES_TP1_ADDRESS_ELEMENTS: list[str] = [
    r"\(F9111\)",
    r"75-77\s+Avenue\s+Marcel\s+Dassault",
    r"33700\s+M\u00e9rignac\s+-\s+France",
    r"Tel\s*:\s*\+33\s+\(0\)5\s+24\s+44\s+77\s+40",
    r"www\.thalesgroup\.com",
]


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


def identify_tp1_pages(
    parsed: ParsedPdf,
    revision_date: str | None,
    cmm_number: str | None = None,
) -> dict[str, str | None]:
    """Mark pages whose footer band carries both the CMM/revision anchor and
    a TP1 marker.

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
    expected_anchors = [anchor for anchor in expected_anchors if anchor]
    if not expected_anchors:
        _logger.warning(
            "tp1_detection_skipped_no_anchor",
            reason="meta_cmm_number et meta_revision_date absents du contexte document",
        )
    page_types: dict[str, str | None] = {}
    for page in parsed.pages:
        page_type: str | None = None
        lines: list[str] = []
        if expected_anchors:
            lines = _footer_lines(page)
            footer_text = " ".join(lines).casefold()
            has_anchor = any(anchor in footer_text for anchor in expected_anchors)
            has_marker = bool(_TP1_MARKER_PATTERN.search(footer_text))
            if has_anchor and has_marker:
                page_type = TP1_PAGE_TYPE
        if expected_anchors and page_type is None:
            # Aide au diagnostic : si zero page n'est jamais classee TP1,
            # compare `footer_lines` a la mise en page reelle du pied de
            # page (anchor et/ou marqueur absents du bandeau detecte).
            _logger.debug(
                "tp1_detection_no_match",
                page=page.page,
                expected_anchors=expected_anchors,
                footer_lines=lines,
            )
        page.page_type = page_type
        page_types[str(page.page)] = page_type
    return page_types


def classify_pages(parsed: ParsedPdf, document: object) -> None:
    """`PAGE_CLASSIFIERS` entry point (see `app.checks.standards`): reads the
    anchors off `document` itself so the generic pipeline never has to know
    what this standard needs to classify a page."""
    identify_tp1_pages(
        parsed,
        getattr(document, "meta_revision_date", None),
        getattr(document, "meta_cmm_number", None),
    )


def _regex_rule(
    code: str,
    topic: str,
    pattern: str,
    *,
    operator: Literal["regex", "regex_exists"] = "regex",
    severity: Literal["info", "warning", "error"] = "warning",
    replacement: str | None = None,
) -> CompiledRule:
    return CompiledRule(
        id=code,
        topic=topic,
        severity=severity,
        execution="deterministic",
        target=_TARGET,
        checks=[
            Check(
                field="text",
                operator=operator,
                expected=pattern,
                replacement=replacement,
            )
        ],
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:{code}",
    )


_RULES_V1 = [
    CompiledRule(
        id="CUSTOM_CMM_NUMBER",
        topic="Numero CMM conforme au contexte du document",
        severity="error",
        execution="deterministic",
        target=_FOOTER_TARGET,
        checks=[
            Check(
                field="text",
                operator="regex_exists",
                expected=_EXPECTED_CMM_PATTERN,
            ),
            Check(
                field="text",
                operator="regex",
                expected=(
                    r"(?<!\w)(?!{{meta_cmm_number}}(?!\w))"
                    + _CMM_NUMBER_PATTERN
                    + r"(?!\w)"
                ),
                replacement="{{meta_cmm_number}}",
            ),
        ],
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:CUSTOM_CMM_NUMBER",
    ),
    CompiledRule(
        id="CUSTOM_TITLE_PAGE_COPYRIGHT",
        topic="Copyright du footer conforme a l'annee de revision",
        severity="error",
        execution="deterministic",
        target=_FOOTER_TARGET,
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
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:CUSTOM_TITLE_PAGE_COPYRIGHT",
    ),
    CompiledRule(
        id="CUSTOM_REVISION_DATE",
        topic="Date de revision du footer conforme au mapping",
        severity="error",
        execution="deterministic",
        target=_FOOTER_TARGET,
        checks=[
            Check(
                field="text",
                operator="regex_exists",
                expected=_EXPECTED_REVISION_DATE_PATTERN,
            ),
            Check(
                field="text",
                operator="regex",
                expected=(
                    r"(?<!\w)(?!{{meta_revision_date}}(?!\w))"
                    + _REVISION_DATE_PATTERN
                    + r"(?!\w)"
                ),
                replacement="{{meta_revision_date}}",
            ),
        ],
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:CUSTOM_REVISION_DATE",
    ),
    CompiledRule(
        id="CUSTOM_TP1_THALES_ADDRESS",
        topic="Adresse THALES exacte sur les pages TP1",
        severity="error",
        execution="deterministic",
        target=_TP1_ADDRESS_TARGET,
        checks=[
            Check(field="text", operator="regex_exists", expected=pattern)
            for pattern in _THALES_TP1_ADDRESS_ELEMENTS
        ],
        source="standard_rule",
        origin_ref=f"{_ORIGIN}:CUSTOM_TP1_THALES_ADDRESS",
    ),
    _regex_rule(
        "CUSTOM_DECIMAL_COMMA",
        "Valeurs decimales doivent etre separees par un point",
        _DECIMAL_COMMA_PATTERN,
        severity="error",
        replacement=r"\1.\2",
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
RULE_METADATA["CUSTOM_DECIMAL_COMMA"] = {
    "description": (
        "Les valeurs numeriques decimales des pages modifiees doivent utiliser "
        "un point comme separateur decimal, et non une virgule."
    ),
    "kind": "regex_flag",
    "severity": "error",
    "message": "Une valeur decimale utilise une virgule au lieu d'un point.",
}


CATALOG: dict[str, list[CompiledRule]] = {"v1": _RULES_V1}


USER_STANDARD_SPEC: dict[str, object] = {
    "code": STANDARD_CODE,
    "label": STANDARD_LABEL,
    "description": STANDARD_DESCRIPTION,
    "versions": CATALOG,
    "metadata": RULE_METADATA,
}