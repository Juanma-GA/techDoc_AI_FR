"""THALES-specific compiled rules.

Add rules to ``_RULES_V1`` and restart the backend. The catalog is synchronized
into the local database at startup.
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
_TP1_REVISION_TARGET = RuleTarget(page="all", region="footer", page_type="TP1")
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
_EXPECTED_TP1_REVISION_NUMBER_PATTERN = (
    r"(?i)(?<!\w)Revision\s+No\.?\s*{{meta_revision_number}}(?!\w)"
    r"(?=[\s\S]*\bFirst\s+Issue\b)"
)
_EXPECTED_TP1_FIRST_ISSUE_PATTERN = (
    r"(?i)(?<!\w)First\s+issue\s*:\s*{{meta_first_issue_date}}(?!\w)"
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
    )


def _required_text_check(
    pattern: str,
    *,
    display: str | None = None,
    anchor: str | None = None,
    anchor_position: Literal["above", "below"] = "above",
) -> Check:
    return Check(
        field="text",
        operator="regex_exists",
        expected=pattern,
        require_all=True,
        expected_display=display,
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


STANDARD_SPEC: dict[str, object] = {
    "code": STANDARD_CODE,
    "label": STANDARD_LABEL,
    "description": STANDARD_DESCRIPTION,
    "versions": CATALOG,
    "metadata": RULE_METADATA,
}