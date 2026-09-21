"""THALES-specific compiled rules.

Add rules to ``_RULES_V1`` and restart the backend. The catalog is synchronized
into the local database at startup.
"""

from __future__ import annotations

import re
from typing import Literal

from app.checks.standards import _thales_revision as revision
from app.core.compiled_rules import (
    Check,
    CompiledRule,
    Condition,
    FieldRef,
    RuleTarget,
)
from app.core.logging import get_logger
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


STANDARD_CODE = "THALES-CUSTOM"
STANDARD_LABEL = "THALES - Regles utilisateur"
STANDARD_DESCRIPTION = (
    "Regles locales editables pour tester des controles sur les documents."
)

_logger = get_logger(__name__)

_TARGET = RuleTarget(page="all", region="full_page")
# Une page inchangee doit conserver sa date d'emission d'origine : corriger
# son contenu obligerait a la redater, donc a la declarer revisee. Les regles
# de contenu ne s'appliquent qu'aux pages que cette revision touche deja.
_MODIFIED_TARGET = RuleTarget(page="all", region="full_page", page_state="modified")
_FOOTER_TARGET = RuleTarget(page="all", region="footer")
_MODIFIED_FOOTER_TARGET = RuleTarget(page="all", region="footer", page_state="modified")
_TP1_REVISION_TARGET = RuleTarget(page="all", region="footer", page_type="TP1")
# full_page (et non footer) : sur ce standard, le bloc adresse THALES est
# positionne hors du bandeau bas-de-page a 25% calcule par `_scope_targets`
# (verifie en prod : le scope "footer" ne recupere qu'une partie du texte
# de la page, l'adresse en est exclue). On reste donc sur le texte brut de
# la page entiere, filtre uniquement par `page_type`.
_TP1_ADDRESS_TARGET = RuleTarget(page="all", region="full_page", page_type="TP1")
_ORIGIN = f"{STANDARD_CODE}:v1"
TP1_PAGE_TYPE = "TP1"
TP2_PAGE_TYPE = "TP2"
_TP2_IMPORTANT_NOTICE_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_type=TP2_PAGE_TYPE,
)
_THALES_LOGO_TARGET = RuleTarget(
    page="all",
    region="full_page",
    excluded_page_types=[TP1_PAGE_TYPE],
)
_TP1_THALES_LOGO_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_type=TP1_PAGE_TYPE,
)
HIGHLIGHTS_PAGE_TYPE = "HIGHLIGHTS"
HIGHLIGHTS_FIRST_PAGE_TYPE = "HIGHLIGHTS_PAGE_1"
INTRODUCTION_PAGE_TYPE = "INTRODUCTION"
REPAIR_PAGE_TYPE = "REPAIR"
TESTING_PAGE_TYPE = "TESTING"
STORAGE_PAGE_TYPE = "STORAGE"
_NOTE_PAGE_TYPES = (REPAIR_PAGE_TYPE, TESTING_PAGE_TYPE, STORAGE_PAGE_TYPE)
_PAGE_TYPE_MARKERS = {
    page_type: re.compile(rf"(?im)^\s*{page_type}\s*$")
    for page_type in _NOTE_PAGE_TYPES
}
_HIGHLIGHTS_PAGE_1_MARKER = re.compile(r"(?i)\bHighlights\s+Page\s+1\b")
_HIGHLIGHTS_PAGE_TYPES = [HIGHLIGHTS_PAGE_TYPE, HIGHLIGHTS_FIRST_PAGE_TYPE]
_INTRODUCTION_PAGE_MARKER = re.compile(r"(?m)^\s*INTRODUCTION\s*$")
_TABLE_OF_CONTENTS_MARKER = re.compile(r"(?im)^\s*TABLE\s+OF\s+CONTENTS\s*$")
_NOTE_INTRODUCTION_TEXT = {
    REPAIR_PAGE_TYPE: (
        "During repair operations, make sure that the environmental conditions "
        "are as follows:"
    ),
    TESTING_PAGE_TYPE: (
        "During testing operations, make sure that the environmental conditions "
        "are as follows:"
    ),
    STORAGE_PAGE_TYPE: (
        "During storage operations, make sure that the environmental conditions "
        "are as follows:"
    ),
}
_HIGHLIGHTS_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_types=_HIGHLIGHTS_PAGE_TYPES,
)
_HIGHLIGHTS_FIRST_PAGE_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_type=HIGHLIGHTS_FIRST_PAGE_TYPE,
)
_HEADER_TARGET = RuleTarget(
    page="all",
    region="header",
    excluded_page_types=[TP1_PAGE_TYPE],
)
_HIGHLIGHTS_PNR_TARGET = RuleTarget(
    page="all",
    region="full_page",
    page_types=_HIGHLIGHTS_PAGE_TYPES,
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
_FORBIDDEN_CONSUMABLES = ["Silica gel", "dessicant bag"]
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
_EXPECTED_HIGHLIGHTS_ATA_PATTERN = r"(?i)(?<!\w)ATA\s+No\.?\s*{{meta_cmm_number}}(?!\w)"
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
_REPAIR_RELATIVE_HUMIDITY = (
    "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00, "
    "F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
)
_STORAGE_TEMPERATURE = (
    "Temperature: Refer to Standard Practices Manual ATA No. 20-02-00, "
    "F9111CMON-A-20-02-00-00A-812A-A – Storage and Transportation of Assemblies."
)
_SHOP_VERIFICATION_AIRBUS = """Shop Verification:

A.  Verification of the procedures in this manual

(1)  The shop verification will be done at the first repair of the equipment."""
_SHOP_VERIFICATION_BOEING = """Shop Verification:

A.  Verification of the procedures in this manual

(1)  Testing and Fault Isolation: shop verification done JUN 24/88."""
_IMPORTANT_NOTICE_TEXT = """IMPORTANT NOTICE
This document and any information contained herein are the sole property of THALES AVS FRANCE SAS and have been disclosed under a License Agreement. They cannot be used, reproduced or disclosed without the prior express written approval of THALES AVS FRANCE SAS.
In particular, they shall not be used in the creation, manufacture, development or derivation of any repairs, modifications, spare parts, design, or configuration changes or to obtain EASA, FAA or any other government or regulatory approval to do so.
Should THALES AVS FRANCE SAS consent be given for reproduction in whole or in part, this notice and the notice set forth on each page of this document shall appear in any such reproduction in whole or in part.
The recipient shall not use this document for any purpose other than the one stated in the relevant applicable License agreement under which it has been disclosed and it shall be returned to THALES AVS FRANCE SAS immediately upon request.
TO BE CONSIDERED VALID FOR PART 145 REQUIREMENTS, ALL MAINTENANCE DOCUMENTATION HAS TO BE IDENTIFIED ON EACH PAGE WITH A WATERMARK AUTHORIZING ITS USE BY THE END USER COMPANY. SUCH WATERMARK MIGHT BE AS FOLLOWS:
\u201cProvided to [USER_ID] for [COMPANY_NAME] only under license agreement [LICENSE_NUMBER] for year [YEAR] only\u201d
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


def _exact_text_pattern(value: str) -> str:
    """Keep wording and punctuation exact while tolerating PDF whitespace."""
    return re.escape(value).replace(r"\ ", r"\s+")


_REPAIR_RELATIVE_HUMIDITY_PATTERN = _exact_text_pattern(_REPAIR_RELATIVE_HUMIDITY)
_STORAGE_TEMPERATURE_PATTERN = _exact_text_pattern(_STORAGE_TEMPERATURE)
_NOTE_PRESSURE_PATTERN = r"\bPressure\s*:"


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
                if (
                    page_name == HIGHLIGHTS_PAGE_TYPE
                    and _HIGHLIGHTS_PAGE_1_MARKER.search(page.text)
                ):
                    page.page_type = HIGHLIGHTS_FIRST_PAGE_TYPE
            elif page.page_type == page_name or (
                page_name == HIGHLIGHTS_PAGE_TYPE
                and page.page_type in _HIGHLIGHTS_PAGE_TYPES
            ):
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


def identify_note_pages(parsed: ParsedPdf) -> dict[str, str | None]:
    """Classify NOTE pages from a standalone REPAIR/TESTING/STORAGE heading."""
    page_types: dict[str, str | None] = {}
    for page in parsed.pages:
        detected_types = [
            page_type
            for page_type, marker in _PAGE_TYPE_MARKERS.items()
            if marker.search(page.text)
        ]
        detected_type = detected_types[0] if len(detected_types) == 1 else None
        if detected_type is not None and (
            page.page_type is None or page.page_type in _NOTE_PAGE_TYPES
        ):
            page.page_type = detected_type
        elif page.page_type in _NOTE_PAGE_TYPES:
            page.page_type = None
        page_types[str(page.page)] = page.page_type
    return page_types


def identify_introduction_pages(parsed: ParsedPdf) -> dict[str, str | None]:
    """Classify pages carrying the standalone INTRODUCTION heading."""
    page_types: dict[str, str | None] = {}
    for page in parsed.pages:
        if page.page_type is None or page.page_type == INTRODUCTION_PAGE_TYPE:
            if (
                _INTRODUCTION_PAGE_MARKER.search(page.text or "")
                and _TABLE_OF_CONTENTS_MARKER.search(page.text or "") is None
            ):
                page.page_type = INTRODUCTION_PAGE_TYPE
            elif page.page_type == INTRODUCTION_PAGE_TYPE:
                page.page_type = None
        page_types[str(page.page)] = page.page_type
    return page_types


def shop_verification_text(document: object | None) -> str:
    manufacturer = str(getattr(document, "meta_manufacturer", "Airbus") or "Airbus")
    return (
        _SHOP_VERIFICATION_BOEING
        if manufacturer.casefold() == "boeing"
        else _SHOP_VERIFICATION_AIRBUS
    )


def shop_verification_section(text: str) -> str:
    start_match = re.search(r"(?im)^\s*Shop\s+Verification\s*:\s*", text)
    if start_match is None:
        return ""
    end_match = re.search(r"(?im)^\s*\d+\.\s+[A-Z]", text[start_match.end() :])
    end = start_match.end() + end_match.start() if end_match is not None else len(text)
    return text[start_match.start() : end].strip()


def shop_verification_matches(text: str, expected: str) -> bool:
    observed = " ".join(shop_verification_section(text).split()).casefold()
    expected_normalized = " ".join(expected.split()).casefold()
    return bool(observed) and expected_normalized in observed


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
        TP2_PAGE_TYPE,
        getattr(document, "meta_revision_date", None),
        getattr(document, "meta_cmm_number", None),
    )
    identify_page_type(
        parsed,
        HIGHLIGHTS_PAGE_TYPE,
        getattr(document, "meta_revision_date", None),
        getattr(document, "meta_cmm_number", None),
    )
    identify_note_pages(parsed)
    identify_introduction_pages(parsed)
    # En dernier : `page.is_modified` conditionne le perimetre des regles de
    # contenu, il doit donc etre connu avant toute execution de regle.
    revision_state(parsed, document)


_REVISION_STATE_ATTR = "_thales_revision_state"


def revision_state(parsed: ParsedPdf, document: object) -> revision.RevisionState:
    """Build (once per parsed document) the cross-source revision state."""
    cached = getattr(parsed, _REVISION_STATE_ATTR, None)
    if cached is not None:
        return cached
    state = revision.build_revision_state(parsed, document)
    setattr(parsed, _REVISION_STATE_ATTR, state)
    _logger.info(
        "thales_revision_state_built",
        available=state.available,
        highlights_pages=list(state.highlights_pages),
        lep_pages=list(state.lep_pages),
        highlights_entries=len(state.highlights),
        lep_entries=len(state.lep),
        footers=len(state.footers),
        modified_pages=[page.page for page in parsed.pages if page.is_modified],
    )
    return state


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
    missing_anchor_position: Literal["above", "below", "same"] = "above",
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
    anchor_position: Literal["above", "below", "same"] = "above",
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


def _required_note_check(
    content_pattern: str,
    *,
    display: str,
    page_type: str,
    anchor: str | None = None,
    anchor_position: Literal["above", "below", "same"] = "above",
) -> Check:
    introduction_pattern = _exact_text_pattern(_NOTE_INTRODUCTION_TEXT[page_type])
    return _required_text_check(
        (
            rf"(?i:\bNOTE\b)\s*:\s*{introduction_pattern}"
            r"(?is:(?:(?!\bNOTE\b).)*?)"
            + content_pattern
        ),
        display=display,
        suggestion_mode="fuzzy",
        anchor=anchor,
        anchor_position=anchor_position,
    )


def _revision_rule(
    code: str,
    topic: str,
    control: str,
    failure_message: str,
    *,
    severity: Literal["info", "warning", "error"] = "error",
) -> CompiledRule:
    return _rule(
        code,
        topic,
        failure_message=failure_message,
        severity=severity,
        only_if=Condition(field="meta_revision_date", state="present"),
        checks=[
            Check(
                field="text",
                operator="revision_consistency",
                expected=control,
            ),
        ],
    )


# Ces controles s'executent en premier : ils etablissent quelles pages la
# revision touche (`page.is_modified`), perimetre dont dependent ensuite
# toutes les regles ciblant `page_state="modified"`.
_REVISION_RULES = [
    _revision_rule(
        "CUSTOM_REVISION_LEP_STAR",
        "Etoile LEP presente pour chaque page revisee ou nouvelle",
        revision.LEP_STAR,
        "etoile absente dans la liste des pages effectives.",
    ),
    _revision_rule(
        "CUSTOM_REVISION_UNDECLARED_STAR",
        "Etoile LEP justifiee par un statut R ou N dans les Highlights",
        revision.UNDECLARED_STAR,
        "etoile LEP sans statut R ou N dans les Highlights.",
    ),
    _revision_rule(
        "CUSTOM_REVISION_LEP_DATE",
        "Date LEP conforme au statut de la page",
        revision.LEP_DATE,
        "date LEP incoherente avec le statut de la page.",
    ),
    _revision_rule(
        "CUSTOM_REVISION_FOOTER_DATE",
        "Date du pied de page conforme aux Highlights et a la LEP",
        revision.FOOTER_DATE,
        "date du pied de page incoherente avec les Highlights et la LEP.",
    ),
    _revision_rule(
        "CUSTOM_FOOTER_PAGE_NUMBER",
        "Numero de page present et conforme dans le pied de page",
        revision.FOOTER_PAGE_NUMBER,
        "numero de page absent ou incoherent dans le pied de page.",
    ),
    _revision_rule(
        "CUSTOM_REVISION_UNDECLARED_PAGE",
        "Page datee de la revision declaree modifiee",
        revision.UNDECLARED_PAGE,
        "page datee de la revision courante sans declaration de modification.",
    ),
    _revision_rule(
        "CUSTOM_REVISION_PAGE_NOT_IN_LEP",
        "Page du document presente dans la liste des pages effectives",
        revision.PAGE_NOT_IN_LEP,
        "page du document absente de la liste des pages effectives.",
        severity="warning",
    ),
    _revision_rule(
        "CUSTOM_REVISION_MODIFIED_PAGE_ABSENT",
        "Page declaree revisee presente dans le document",
        revision.MODIFIED_PAGE_ABSENT,
        "page declaree revisee introuvable dans le document.",
        severity="warning",
    ),
    _revision_rule(
        "CUSTOM_HIGHLIGHTS_PAGE_PAIRING",
        "Pages Highlights declarees par couple impaire/paire",
        revision.HIGHLIGHTS_PAIRING,
        "page Highlights declaree sans sa page paire ou impaire associee.",
        severity="warning",
    ),
    _revision_rule(
        "CUSTOM_HIGHLIGHTS_PAGE_LABEL_FORMAT",
        "Libelle Page/Pages et alignement dans les Highlights",
        revision.HIGHLIGHTS_PAGE_LABEL,
        "libelle Page/Pages ou alignement non conforme dans les Highlights.",
        severity="warning",
    ),
]


_RULES_V1 = [
    *_REVISION_RULES,
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
        "CUSTOM_CMM_NUMBER_FONT_SIZE",
        "Taille de police du numero CMM (ATA)",
        failure_message="taille de police du numero CMM non conforme.",
        target=_FOOTER_TARGET,
        severity="warning",
        only_if=Condition(field="meta_cmm_number", state="present"),
        checks=[
            Check(
                field="cmm_number",
                operator="font_size_equals",
                expected=23,
                require_all=True,
            ),
        ],
    ),
    _rule(
        "CUSTOM_THALES_LOGO_FONT_SIZE",
        "Taille du logo THALES sur les pages hors TP1",
        failure_message="taille du logo THALES non conforme hors TP1.",
        target=_THALES_LOGO_TARGET,
        severity="warning",
        checks=[
            Check(
                field="thales_logo_t",
                operator="font_size_equals",
                expected=31,
                require_all=True,
            ),
        ],
    ),
    _rule(
        "CUSTOM_TP1_THALES_LOGO_FONT_SIZE",
        "Taille du logo THALES sur les pages TP1",
        failure_message="taille du logo THALES non conforme sur TP1.",
        target=_TP1_THALES_LOGO_TARGET,
        severity="warning",
        checks=[
            Check(
                field="thales_logo_t",
                operator="font_size_equals",
                expected=36,
                require_all=True,
            ),
        ],
    ),
    _rule(
        "CUSTOM_TP2_IMPORTANT_NOTICE",
        "Important Notice TP2 conforme au modele ATA100",
        failure_message="Important Notice TP2 non conforme au modele ATA100.",
        target=_TP2_IMPORTANT_NOTICE_TARGET,
        severity="error",
        checks=[
            Check(
                field="important_notice",
                operator="normalized_equals",
                expected=_IMPORTANT_NOTICE_TEXT,
                normalization=["unicode", "spaces", "line_breaks", "trim"],
            ),
        ],
    ),
    _rule(
        "CUSTOM_TITLE_PAGE_COPYRIGHT",
        "Copyright du footer conforme a l'annee de revision",
        failure_message="Copyright du footer non conforme",
        target=_MODIFIED_FOOTER_TARGET,
        severity="warning",
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
        severity="warning",
        checks=[
            _required_text_check(
                _EXPECTED_TP1_FIRST_ISSUE_PATTERN,
                display="First issue: {{meta_first_issue_date}}",
                anchor=r"(?i)\bFirst\s+issue\s*:",
                anchor_position="same",
            ),
        ],
    ),
    _rule(
        "CUSTOM_HIGHLIGHTS_REVISION_HEADER",
        "En-tete de revision present au-dessus du tableau Highlights",
        failure_message="En-tete de revision Highlights non conforme.",
        target=_HIGHLIGHTS_TARGET,
        severity="warning",
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
        "CUSTOM_INTRODUCTION_SHOP_VERIFICATION",
        "Shop Verification conforme au constructeur du mapping",
        failure_message="Shop Verification INTRODUCTION non conforme.",
        target=RuleTarget(
            page="all",
            region="full_page",
            page_type=INTRODUCTION_PAGE_TYPE,
        ),
        severity="error",
        only_if=Condition(field="meta_manufacturer", state="present"),
        checks=[
            Check(
                field="text",
                operator="shop_verification",
                expected="manufacturer_mapping",
                require_all=True,
            ),
        ],
    ),
    _rule(
        "CUSTOM_HIGHLIGHTS_ATA_NUMBER",
        "Numero ATA present sur la premiere page Highlights",
        failure_message="numero ATA Highlights absent ou non conforme.",
        target=_HIGHLIGHTS_FIRST_PAGE_TARGET,
        severity="error",
        only_if=Condition(field="meta_cmm_number", state="present"),
        checks=[
            _required_text_check(
                _EXPECTED_HIGHLIGHTS_ATA_PATTERN,
                display="ATA No {{meta_cmm_number}}",
                suggestion_mode="single",
                anchor=r"(?i)\bATA\s+No\b",
                anchor_position="same",
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
        "CUSTOM_REPAIR_NOTE",
        "Introduction et categories obligatoires dans les NOTE des pages REPAIR",
        failure_message="introduction ou categories NOTE REPAIR non conformes.",
        target=RuleTarget(page="all", region="full_page", page_type=REPAIR_PAGE_TYPE),
        severity="error",
        checks=[
            _required_note_check(
                _NOTE_PRESSURE_PATTERN,
                display="Pressure:",
                page_type=REPAIR_PAGE_TYPE,
            ),
            _required_note_check(
                _REPAIR_RELATIVE_HUMIDITY_PATTERN,
                display=_REPAIR_RELATIVE_HUMIDITY,
                page_type=REPAIR_PAGE_TYPE,
            ),
        ],
    ),
    _rule(
        "CUSTOM_TESTING_NOTE",
        "Introduction et categories obligatoires dans les NOTE des pages TESTING",
        failure_message="introduction ou categories NOTE TESTING non conformes.",
        target=RuleTarget(page="all", region="full_page", page_type=TESTING_PAGE_TYPE),
        severity="error",
        checks=[
            _required_note_check(
                _NOTE_PRESSURE_PATTERN,
                display="Pressure:",
                page_type=TESTING_PAGE_TYPE,
            ),
            _required_note_check(
                _REPAIR_RELATIVE_HUMIDITY_PATTERN,
                display=_REPAIR_RELATIVE_HUMIDITY,
                page_type=TESTING_PAGE_TYPE,
            ),
            _required_note_check(
                r"\bTemperature\b",
                display="Temperature",
                page_type=TESTING_PAGE_TYPE,
            ),
        ],
    ),
    _rule(
        "CUSTOM_STORAGE_NOTE",
        "Introduction et categories obligatoires dans les NOTE des pages STORAGE",
        failure_message="introduction ou categories NOTE STORAGE non conformes.",
        target=RuleTarget(page="all", region="full_page", page_type=STORAGE_PAGE_TYPE),
        severity="error",
        checks=[
            _required_note_check(
                _NOTE_PRESSURE_PATTERN,
                display="Pressure:",
                page_type=STORAGE_PAGE_TYPE,
            ),
            _required_note_check(
                _REPAIR_RELATIVE_HUMIDITY_PATTERN,
                display=_REPAIR_RELATIVE_HUMIDITY,
                page_type=STORAGE_PAGE_TYPE,
            ),
            _required_note_check(
                _STORAGE_TEMPERATURE_PATTERN,
                display=_STORAGE_TEMPERATURE,
                page_type=STORAGE_PAGE_TYPE,
                anchor=r"(?i)\bRelative\s+humidity\s*:",
                anchor_position="below",
            ),
        ],
    ),
    _rule(
        "CUSTOM_TP1_THALES_ADDRESS",
        "Adresse THALES exacte sur les pages TP1",
        failure_message="adresse THALES non conforme.",
        target=_TP1_ADDRESS_TARGET,
        severity="warning",
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
        target=_MODIFIED_TARGET,
        severity="warning",
        replacement=r"\1.\2",
    ),
    _rule(
        "CUSTOM_TEMPERATURE_FAHRENHEIT",
        "Temperature en deg. C accompagnee de sa conversion en deg. F",
        failure_message="conversion Fahrenheit absente pour la temperature.",
        pattern=_TEMPERATURE_WITHOUT_FAHRENHEIT_PATTERN,
        target=_MODIFIED_TARGET,
        severity="error",
        replacement="{{temperature_fahrenheit}}",
    ),
    _rule(
        "CUSTOM_BAR_PSI_CONVERSION",
        "Pression en bar accompagnee de sa conversion en p.s.i.",
        failure_message=(
            "conversion p.s.i. absente ou incorrecte pour une pression en bar."
        ),
        target=_MODIFIED_TARGET,
        severity="error",
        checks=[
            Check(
                field="text",
                operator="pressure_conversion",
                expected="bar_to_psi",
            ),
        ],
    ),
    _rule(
        "CUSTOM_FORBIDDEN_CONSUMABLES",
        "Consommables a supprimer",
        failure_message="consommable a supprimer.",
        target=_MODIFIED_TARGET,
        severity="error",
        checks=[
            Check(
                field="text",
                operator="contains_none",
                expected=_FORBIDDEN_CONSUMABLES,
                replacement="",
            ),
        ],
    ),
    _rule(
        "CUSTOM_NO_DEGREE_C_SYMBOL",
        "Unite de temperature C ecrite au format deg. C",
        failure_message="unite °C interdite, utiliser deg. C.",
        pattern=_DEGREE_C_PATTERN,
        target=_MODIFIED_TARGET,
        severity="info",
        replacement="deg. C",
    ),
    _rule(
        "CUSTOM_NO_DEGREE_F_SYMBOL",
        "Unite de temperature F ecrite au format deg. F",
        failure_message="unite °F interdite, utiliser deg. F.",
        pattern=_DEGREE_F_PATTERN,
        target=_MODIFIED_TARGET,
        severity="info",
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
        "Le footer des pages modifiees par la revision doit contenir le "
        "copyright THALES avec l'annee de debut 1966 et l'annee de revision "
        "du document."
    ),
    "kind": "field_required",
    "severity": "warning",
    "message": "Le copyright du footer est absent ou une annee est incorrecte.",
}
RULE_METADATA["CUSTOM_INTRODUCTION_SHOP_VERIFICATION"] = {
    "description": (
        "La page INTRODUCTION doit contenir le bloc Shop Verification attendu "
        "pour le constructeur choisi dans le mapping (Airbus ou Boeing)."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Le bloc Shop Verification de l'INTRODUCTION est absent ou incorrect.",
}
RULE_METADATA["CUSTOM_TP1_THALES_ADDRESS"] = {
    "description": (
        "Chaque page identifiee TP1 doit contenir exactement l'adresse THALES "
        "de reference."
    ),
    "kind": "field_required",
    "severity": "warning",
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
    "severity": "warning",
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
    "severity": "warning",
    "message": (
        "L'en-tete de revision Highlights est absent, incorrect ou place "
        "apres le tableau."
    ),
}
RULE_METADATA["CUSTOM_HIGHLIGHTS_ATA_NUMBER"] = {
    "description": (
        "La premiere page Highlights doit contenir le numero ATA correspondant "
        "au numero CMM du mapping du document."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Le numero ATA de la premiere page Highlights est absent ou incorrect.",
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
    "severity": "warning",
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
RULE_METADATA["CUSTOM_BAR_PSI_CONVERSION"] = {
    "description": (
        "Toute pression exprimee en bar doit etre suivie entre parentheses "
        "de sa conversion numerique en p.s.i."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "La pression en bar doit etre suivie de sa conversion en p.s.i.",
}
RULE_METADATA["CUSTOM_FORBIDDEN_CONSUMABLES"] = {
    "description": (
        "Les references aux consommables interdits doivent etre supprimees."
    ),
    "kind": "regex_flag",
    "severity": "error",
    "message": "Consommable a supprimer.",
}
RULE_METADATA["CUSTOM_NO_DEGREE_C_SYMBOL"] = {
    "description": "Le symbole °C doit etre ecrit sous la forme deg. C.",
    "kind": "regex_flag",
    "severity": "info",
    "message": "Le symbole °C est interdit : utiliser deg. C.",
}
RULE_METADATA["CUSTOM_NO_DEGREE_F_SYMBOL"] = {
    "description": "Le symbole °F doit etre ecrit sous la forme deg. F.",
    "kind": "regex_flag",
    "severity": "info",
    "message": "Le symbole °F est interdit : utiliser deg. F.",
}
RULE_METADATA["CUSTOM_REVISION_LEP_STAR"] = {
    "description": (
        "Toute page declaree revisee (R) ou nouvelle (N) dans les Highlights "
        "doit porter une etoile apres sa date dans la liste des pages "
        "effectives."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Page revisee dans les Highlights sans etoile dans la LEP.",
}
RULE_METADATA["CUSTOM_REVISION_UNDECLARED_STAR"] = {
    "description": (
        "Une etoile dans la liste des pages effectives signale une page "
        "modifiee : cette page doit etre declaree R ou N dans les Highlights."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Etoile LEP sur une page non declaree revisee dans les Highlights.",
}
RULE_METADATA["CUSTOM_REVISION_LEP_DATE"] = {
    "description": (
        "La date de la liste des pages effectives doit valoir la date de "
        "revision du mapping pour une page revisee ou nouvelle, et rester la "
        "derniere date d'emission connue pour une page inchangee."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Date LEP incoherente avec le statut de la page.",
}
RULE_METADATA["CUSTOM_REVISION_FOOTER_DATE"] = {
    "description": (
        "Le pied de page doit porter la date de revision du mapping pour une "
        "page revisee ou nouvelle, et la date declaree dans la liste des pages "
        "effectives pour une page inchangee."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Date du pied de page incoherente avec les Highlights et la LEP.",
}
RULE_METADATA["CUSTOM_REVISION_UNDECLARED_PAGE"] = {
    "description": (
        "Une page qui porte la date de la revision courante doit etre declaree "
        "modifiee, dans les Highlights (R ou N) et par une etoile dans la LEP."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Page datee de la revision courante sans declaration de modification.",
}
RULE_METADATA["CUSTOM_REVISION_PAGE_NOT_IN_LEP"] = {
    "description": (
        "Toute page du document doit figurer dans la liste des pages "
        "effectives."
    ),
    "kind": "field_required",
    "severity": "warning",
    "message": "Page du document absente de la liste des pages effectives.",
}
RULE_METADATA["CUSTOM_REVISION_MODIFIED_PAGE_ABSENT"] = {
    "description": (
        "Toute page declaree revisee ou nouvelle dans les Highlights doit "
        "exister dans le document et s'identifier dans son pied de page."
    ),
    "kind": "field_required",
    "severity": "warning",
    "message": "Page declaree revisee introuvable dans le document.",
}
RULE_METADATA["CUSTOM_FOOTER_PAGE_NUMBER"] = {
    "description": (
        "Chaque page doit afficher son numero dans le pied de page. Les pages "
        "LEP, ROR, Highlights et Title Page sont verifiees contre leur prefixe "
        "et leur ordre attendu (LEP Page 1, ROR Page 1, TP 1, etc.)."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "Le numero de page du pied de page est absent ou incorrect.",
}
RULE_METADATA["CUSTOM_HIGHLIGHTS_PAGE_PAIRING"] = {
    "description": (
        "Les Highlights declarent les pages par couple : une page impaire est "
        "suivie de la page paire correspondante, et une page paire est "
        "precedee de son impaire."
    ),
    "kind": "field_required",
    "severity": "warning",
    "message": "Page Highlights declaree sans sa page paire ou impaire associee.",
}
RULE_METADATA["CUSTOM_HIGHLIGHTS_PAGE_LABEL_FORMAT"] = {
    "description": (
        "Une plage de pages s'ecrit « Pages 701 to 704 » et une page unique "
        "« Page  401 », avec deux espaces pour conserver l'alignement des "
        "numeros."
    ),
    "kind": "field_required",
    "severity": "warning",
    "message": "Libelle Page/Pages ou alignement non conforme dans les Highlights.",
}


CATALOG: dict[str, list[CompiledRule]] = {"v1": _RULES_V1}


STANDARD_SPEC: dict[str, object] = {
    "code": STANDARD_CODE,
    "label": STANDARD_LABEL,
    "description": STANDARD_DESCRIPTION,
    "versions": CATALOG,
    "metadata": RULE_METADATA,
}
RULE_METADATA["CUSTOM_REPAIR_NOTE"] = {
    "description": (
        "Chaque page REPAIR doit commencer sa NOTE par l'introduction "
        "operationnelle attendue et contenir les categories Pressure et "
        "Relative humidity avec la valeur de reference."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": (
        "L'introduction ou les categories NOTE de la page REPAIR sont absentes "
        "ou incorrectes."
    ),
}
RULE_METADATA["CUSTOM_TESTING_NOTE"] = {
    "description": (
        "Chaque page TESTING doit commencer sa NOTE par l'introduction "
        "operationnelle attendue et contenir les categories Pressure, Relative "
        "humidity et Temperature."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": (
        "L'introduction ou les categories NOTE de la page TESTING sont absentes "
        "ou incorrectes."
    ),
}
RULE_METADATA["CUSTOM_STORAGE_NOTE"] = {
    "description": (
        "Chaque page STORAGE doit commencer sa NOTE par l'introduction "
        "operationnelle attendue et contenir les categories Pressure, Relative "
        "humidity et Temperature avec les valeurs de reference."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": (
        "L'introduction ou les categories NOTE de la page STORAGE sont absentes "
        "ou incorrectes."
    ),
}
RULE_METADATA["CUSTOM_CMM_NUMBER_FONT_SIZE"] = {
    "description": (
        "Le numero CMM (ATA) present dans le footer doit utiliser une taille "
        "de police de 23 pt."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "La taille de police du numero CMM (ATA) n'est pas 23 pt.",
}
RULE_METADATA["CUSTOM_THALES_LOGO_FONT_SIZE"] = {
    "description": (
        "Le T de la police Thales en debut de page doit avoir une taille "
        "de 31 pt hors pages TP1."
    ),
    "kind": "field_required",
    "severity": "warning",
    "message": "La taille du logo THALES hors TP1 n'est pas 31 pt.",
}
RULE_METADATA["CUSTOM_TP1_THALES_LOGO_FONT_SIZE"] = {
    "description": (
        "Le T de la police Thales en debut de page TP1 doit avoir une taille "
        "de 36 pt."
    ),
    "kind": "field_required",
    "severity": "warning",
    "message": "La taille du logo THALES sur TP1 n'est pas 36 pt.",
}
RULE_METADATA["CUSTOM_TP2_IMPORTANT_NOTICE"] = {
    "description": (
        "Le bloc IMPORTANT NOTICE de la page TP2 doit correspondre exactement "
        "au modele ATA100, hors differences de retours a la ligne et d'espaces."
    ),
    "kind": "field_required",
    "severity": "error",
    "message": "L'Important Notice de la page TP2 n'est pas conforme au modele ATA100.",
}
