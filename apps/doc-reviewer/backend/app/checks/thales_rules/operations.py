"""THALES operations registered through the generic client-operation contract."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from statistics import median
from typing import Any

from app.checks.client_bundle import ClientOperation, OperationResult
from . import revision_engine as revision
from .rules import (
    DOCUMENT_TYPE_PATTERN,
    DOCUMENT_TYPES,
    HIGHLIGHTS_DOCUMENT_TYPE_PATTERN,
)
from app.core.logging import get_logger
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, PdfLine


_logger = get_logger(__name__)
_REVISION_STATE_ATTR = "_thales_revision_state"
HIGHLIGHTS_HOLDER_PREFIX = "TO: HOLDER OF "
_SHOP_VERIFICATION_AIRBUS = """Shop Verification:

A.  Verification of the procedures in this manual

(1)  The shop verification will be done at the first repair of the equipment."""
_SHOP_VERIFICATION_BOEING = """Shop Verification:

A.  Verification of the procedures in this manual

(1)  Testing and Fault Isolation: shop verification done JUN 24/88."""
_HIGHLIGHTS_CONTENT_MARKER = re.compile(r"(?im)^\s*HIGHLIGHTS\s*$")
_HIGHLIGHTS_HOLDER_RE = re.compile(r"(?i)^TO\s*:\s*HOLDER\s+OF\s+")
_TP1_PART_NUMBER_RE = re.compile(r"(?i)^\s*PART\s+NUMBERS?\s*:?\s*$")
_HIGHLIGHTS_ATA_LINE_RE = re.compile(r"(?im)^\s*ATA\s+No\b[^\r\n]*")
_HIGHLIGHTS_LEGEND_RE = re.compile(r"(?i)\bN\s*:\s*New\b.*\bD\s*:\s*Deleted\b")
_HIGHLIGHTS_FOOTER_LABEL_RE = re.compile(r"(?i)\bHighlights(?:\s+Page\s+\d+)?\b")
_HIGHLIGHTS_FOOTER_CMM_RE = re.compile(r"(?i)(?<!\d)\d{2}-\d{2}-\d{2}(?!\d)")
_HIGHLIGHTS_FOOTER_COPYRIGHT_RE = re.compile(r"(?i)\bTHALES\s+AVS\s+FRANCE\b")
_HIGHLIGHTS_FOOTER_BAND_MIN_HEIGHT = 80.0
_HIGHLIGHTS_FOOTER_LINE_TOLERANCE = 3.0
_HIGHLIGHTS_FOOTER_DATA_DISTANCE = 80.0
_HIGHLIGHTS_LEGEND_FOOTER_EXPECTED = (
    "la legende N: New - D: Deleted ... doit se terminer juste avant le pied "
    "de page, sans ligne de texte intercalaire"
)
_COPYRIGHT_POSITION_MARKER_RE = re.compile(r"(?i)(?:\u00a9|\bcopyright\b)")
_POINTS_PER_CENTIMETER = 72.0 / 2.54
_COPYRIGHT_POSITION_ODD_X_CM = 3.03
_COPYRIGHT_POSITION_EVEN_X_CM = 1.76
_COPYRIGHT_POSITION_Y_CM = 26.51
_COPYRIGHT_POSITION_TOLERANCE_CM = 0.10
_COPYRIGHT_POSITION_EXPECTED = (
    "pages impaires: x=3.03 cm, y=26.51 cm; pages paires: "
    "x=1.76 cm, y=26.51 cm (tolerance +/- 0.10 cm)"
)
_JUSTIFICATION_EXPECTED = "visuellement justifie a gauche et a droite, hors derniere ligne"
_JUSTIFICATION_MIN_LINE_CHARACTERS = 24
_JUSTIFICATION_HORIZONTAL_TOLERANCE = 3.0
_JUSTIFICATION_MULTICOLUMN_TOLERANCE = 40.0
_PARAGRAPH_LIST_ITEM_MARKER = re.compile(
    r"^\s*(?:[-*]|\u2022|\u2013|\u2014|\(\d+\)|\d+[.)]|[A-Z][.)])\s+"
)
_PARAGRAPH_TABLE_HEADER_MARKER = re.compile(r"^\s*[A-Z][A-Z0-9 /&()_\-]{1,}\s*$")
_TABLE_OF_CONTENTS_MARKER = re.compile(r"(?im)^\s*TABLE\s+OF\s+CONTENTS\s*$")
_CHAPTER_HEADING_RE = re.compile(r"^\s*(?P<number>\d+)\.\s+(?P<title>.+?)\s*$")
_CHAPTER_TITLE_CONNECTORS = frozenset(
    {
        "a", "an", "and", "as", "at", "by", "de", "des", "du", "et",
        "for", "from", "in", "la", "le", "les", "of", "on", "or",
        "the", "to", "with",
    }
)
_DELETED_DESCRIPTION_RE = re.compile(r"(?i)\b(?:chapter|page)\s+deleted\b")
_ILLUSTRATED_PARTS_LIST_RE = re.compile(r"(?i)\billustrated\s+parts\s+list\b")
_LIST_OF_MATERIALS_TITLE_RE = re.compile(r"(?im)^\s*LIST\s+OF\s+MATERIALS\s*$")
_SUPPLIERS_HEADER_RE = re.compile(r"(?i)^SUPPLIERS?\s+TRADE\s+NAME\b")
_NUMERICAL_INDEX_PAGE_RE = re.compile(
    r"(?i)^NI/NUM\s+(?P<manual>.+?)\s+(?P<page>\d+)$"
)
_NI_HEADER_LABELS = frozenset(
    {"PART NUMBER", "AIRLINE", "STOCK NO.", "FIGURE", "ITEM", "TTL", "REQ"}
)


def shop_verification_text(document: object | None) -> str:
    manufacturer = str(getattr(document, "meta_manufacturer", "Airbus") or "Airbus")
    return (
        _SHOP_VERIFICATION_BOEING
        if manufacturer.casefold() == "boeing"
        else _SHOP_VERIFICATION_AIRBUS
    )


def shop_verification_section(text: str) -> str:
    start_match = re.search(
        r"(?im)^\s*(?:\d+(?:\.\d+)*[.)]?\s+)?Shop\s+Verification\s*:?\s*",
        text,
    )
    if start_match is None:
        return ""
    end_match = re.search(r"(?im)^\s*\d+\.\s+[A-Z]", text[start_match.end() :])
    end = start_match.end() + end_match.start() if end_match is not None else len(text)
    return text[start_match.start() : end].strip()


def shop_verification_matches(text: str, expected: str) -> bool:
    observed = " ".join(re.findall(r"[a-z0-9]+", shop_verification_section(text).casefold()))
    expected_normalized = " ".join(re.findall(r"[a-z0-9]+", expected.casefold()))
    return bool(observed) and expected_normalized in observed


def highlights_content(text: str) -> str:
    marker = _HIGHLIGHTS_CONTENT_MARKER.search(text)
    return text[marker.end() :].lstrip() if marker is not None else ""


def tp1_title(parsed: ParsedPdf | None) -> str | None:
    if parsed is None:
        return None
    for page in parsed.pages:
        if page.page_type != "TP1":
            continue
        part_number = next(
            (
                span
                for span in page.spans
                if _TP1_PART_NUMBER_RE.match(" ".join(span.text.split()))
            ),
            None,
        )
        if part_number is None:
            continue
        part_center = (part_number.bbox[0] + part_number.bbox[2]) / 2
        candidates = [
            span
            for span in page.spans
            if span.bbox[3] <= part_number.bbox[1]
            and len(span.text.strip()) > 2
            and ("bold" in span.font.casefold() or span.size >= 16.0)
            and span.text.strip().casefold() not in {"t", "tp 1", "tp1"}
        ]
        if not candidates:
            continue
        title_span = max(
            candidates,
            key=lambda span: (
                float(span.size),
                -abs((span.bbox[0] + span.bbox[2]) / 2 - part_center),
                span.bbox[3],
            ),
        )
        return " ".join(title_span.text.split())
    return None


def highlights_holder_expected(parsed: ParsedPdf | None) -> str | None:
    title = tp1_title(parsed)
    return f"{HIGHLIGHTS_HOLDER_PREFIX}{title}" if title else None


def highlights_holder_observed(text: str) -> str:
    return next(
        (
            line.strip()
            for line in text.splitlines()
            if _HIGHLIGHTS_HOLDER_RE.match(line.strip())
        ),
        "",
    )


def highlights_holder_matches(text: str, expected: str) -> bool:
    observed = " ".join(highlights_holder_observed(text).split()).casefold()
    expected_normalized = " ".join(expected.split()).casefold()
    return bool(observed) and observed.startswith(expected_normalized)


def highlights_document_type_expected(text: str) -> str | None:
    match = re.search(DOCUMENT_TYPE_PATTERN, text)
    if match is None:
        return None
    observed = " ".join(match.group(0).split()).casefold()
    return next(
        (
            document_type
            for document_type in DOCUMENT_TYPES
            if document_type.casefold() == observed
        ),
        None,
    )


def highlights_document_type_observed(text: str) -> str:
    ata_match = _HIGHLIGHTS_ATA_LINE_RE.search(text)
    if ata_match is None:
        return ""
    previous_lines = [
        line.strip()
        for line in text[: ata_match.start()].splitlines()
        if line.strip()
    ]
    previous_line = previous_lines[-1] if previous_lines else ""
    return previous_line if re.search(r"(?i)\bMANUAL\b", previous_line) else ""


def highlights_document_type_matches(text: str) -> bool:
    return re.search(HIGHLIGHTS_DOCUMENT_TYPE_PATTERN, text) is not None


def _highlights_visual_lines(
    page: ParsedPage,
) -> list[tuple[str, tuple[float, float, float, float]]]:
    source_lines = [
        (line.text, line.bbox)
        for line in page.lines
        if line.text.strip() and line.bbox[3] > line.bbox[1]
    ]
    if not source_lines:
        source_lines = [
            (span.text, span.bbox)
            for span in page.spans
            if span.text.strip() and span.bbox[3] > span.bbox[1]
        ]

    grouped: list[
        tuple[float, list[str], tuple[float, float, float, float]]
    ] = []
    for text, bbox in sorted(
        source_lines,
        key=lambda item: ((item[1][1] + item[1][3]) / 2, item[1][0]),
    ):
        center_y = (bbox[1] + bbox[3]) / 2
        if grouped and abs(center_y - grouped[-1][0]) <= _HIGHLIGHTS_FOOTER_LINE_TOLERANCE:
            previous_center, texts, previous_bbox = grouped[-1]
            texts.append(text.strip())
            grouped[-1] = (
                previous_center,
                texts,
                (
                    min(previous_bbox[0], bbox[0]),
                    min(previous_bbox[1], bbox[1]),
                    max(previous_bbox[2], bbox[2]),
                    max(previous_bbox[3], bbox[3]),
                ),
            )
        else:
            grouped.append((center_y, [text.strip()], bbox))

    return [(" ".join(texts), bbox) for _center_y, texts, bbox in grouped]


def _highlights_footer_start(
    lines: list[tuple[str, tuple[float, float, float, float]]],
) -> float | None:
    if not lines:
        return None
    min_y = min(bbox[1] for _text, bbox in lines)
    max_y = max(bbox[3] for _text, bbox in lines)
    footer_band_top = max_y - max(
        (max_y - min_y) * 0.25,
        _HIGHLIGHTS_FOOTER_BAND_MIN_HEIGHT,
    )
    footer_band = [
        (text, bbox)
        for text, bbox in lines
        if bbox[3] >= footer_band_top
    ]
    footer_labels = [
        (text, bbox)
        for text, bbox in footer_band
        if _HIGHLIGHTS_FOOTER_LABEL_RE.search(text)
    ]
    if not footer_labels:
        return None

    footer_label_center = max(
        (bbox[1] + bbox[3]) / 2 for _text, bbox in footer_labels
    )
    footer_anchor_centers = [footer_label_center]
    for text, bbox in footer_band:
        center_y = (bbox[1] + bbox[3]) / 2
        before_footer_label = (
            center_y <= footer_label_center + _HIGHLIGHTS_FOOTER_LINE_TOLERANCE
        )
        is_copyright = bool(_HIGHLIGHTS_FOOTER_COPYRIGHT_RE.search(text))
        is_nearby_footer_data = (
            abs(center_y - footer_label_center) <= _HIGHLIGHTS_FOOTER_DATA_DISTANCE
            and (
                _HIGHLIGHTS_FOOTER_CMM_RE.search(text)
                or revision.parse_date(text) is not None
            )
        )
        if before_footer_label and (is_copyright or is_nearby_footer_data):
            footer_anchor_centers.append(center_y)
    return min(footer_anchor_centers)


def _paragraphs_from_pdf_page(page: ParsedPage) -> list[list[PdfLine]]:
    lines_by_block: dict[int, list[PdfLine]] = defaultdict(list)
    for line in page.lines:
        x0, y0, x1, y1 = line.bbox
        if x1 <= x0 or y1 <= y0:
            continue
        if abs(line.direction[1]) > 0.02 or abs(abs(line.direction[0]) - 1.0) > 0.02:
            continue
        if page.page_height > 0 and (
            y0 < page.page_height * 0.08 or y1 > page.page_height * 0.94
        ):
            continue
        lines_by_block[line.block_index].append(line)

    paragraphs: list[list[PdfLine]] = []
    for block_lines in lines_by_block.values():
        ordered_lines = sorted(block_lines, key=lambda item: item.line_index)
        if _pdf_block_has_repeated_columns(ordered_lines):
            continue
        current: list[PdfLine] = []
        for line in ordered_lines:
            if current:
                previous = current[-1]
                line_height = max(
                    previous.bbox[3] - previous.bbox[1],
                    line.bbox[3] - line.bbox[1],
                    1.0,
                )
                if (
                    line.bbox[1] - previous.bbox[1] > max(18.0, line_height * 1.8)
                    or _PARAGRAPH_LIST_ITEM_MARKER.match(line.text) is not None
                    or _PARAGRAPH_TABLE_HEADER_MARKER.match(line.text) is not None
                ):
                    paragraphs.append(current)
                    current = []
            current.append(line)
        if current:
            paragraphs.append(current)
    return paragraphs


def _pdf_block_has_repeated_columns(lines: list[PdfLine]) -> bool:
    visual_rows: list[list[PdfLine]] = []
    row_centers: list[float] = []
    for line in sorted(lines, key=lambda item: (item.bbox[1], item.bbox[0])):
        center_y = (line.bbox[1] + line.bbox[3]) / 2
        if row_centers and abs(center_y - row_centers[-1]) <= 3.0:
            visual_rows[-1].append(line)
        else:
            visual_rows.append([line])
            row_centers.append(center_y)

    wide_gap_rows = 0
    for row in visual_rows:
        row_lines = sorted(row, key=lambda item: item.bbox[0])
        if any(
            current.bbox[0] - previous.bbox[2] > _JUSTIFICATION_MULTICOLUMN_TOLERANCE
            for previous, current in zip(row_lines, row_lines[1:])
        ):
            wide_gap_rows += 1
    return wide_gap_rows >= 2


def _paragraph_justification_issue(
    lines: list[PdfLine],
) -> tuple[bool, PdfLine | None] | None:
    if len(lines) < 3:
        return None
    measurable = [
        (index, line)
        for index, line in enumerate(lines[:-1])
        if len(re.sub(r"\W", "", line.text)) >= _JUSTIFICATION_MIN_LINE_CHARACTERS
    ]
    interior_lines = [line for index, line in measurable if index > 0]
    if len(measurable) < 2:
        return None

    right_edges = [line.bbox[2] for _index, line in measurable]
    paragraph_width = max(line.bbox[2] for _index, line in measurable) - min(
        line.bbox[0] for _index, line in measurable
    )
    right_tolerance = max(4.0, paragraph_width * 0.015)
    expected_right = median(right_edges)
    for _index, line in measurable:
        if abs(line.bbox[2] - expected_right) > right_tolerance:
            return False, line

    if len(interior_lines) >= 2:
        left_edges = [line.bbox[0] for line in interior_lines]
        expected_left = median(left_edges)
        for line in interior_lines:
            if abs(line.bbox[0] - expected_left) > _JUSTIFICATION_HORIZONTAL_TOLERANCE:
                return False, line
    return True, None


def _paragraph_justification_findings(
    context: Any,
) -> tuple[list[OperationResult], int, list[ParsedPage]]:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed_pdf, ParsedPdf):
        return [], 0, []

    targets = tuple(getattr(context, "targets", ()))
    if not targets:
        return [], 0
    target_pages = {target.raw_page for target in targets}
    pages = [page for page in parsed_pdf.pages if page.page in target_pages]
    text_by_page = {target.raw_page: target.text for target in targets}
    checked_paragraphs = 0
    findings: list[OperationResult] = []
    for page in pages:
        page_text = page.text or ""
        if (
            _TABLE_OF_CONTENTS_MARKER.search(page_text)
            or revision._is_lep_page(page)
            or revision._is_highlights_page(page)
            or revision._is_ror_page(page)
        ):
            continue
        for paragraph in _paragraphs_from_pdf_page(page):
            assessment = _paragraph_justification_issue(paragraph)
            if assessment is None:
                continue
            checked_paragraphs += 1
            is_justified, issue_line = assessment
            if is_justified:
                continue
            assert issue_line is not None
            original = issue_line.text.strip()
            if not original:
                continue
            start = text_by_page.get(page.page, "").find(original)
            findings.append(
                OperationResult(
                    status="FAIL",
                    observed=original,
                    expected=_JUSTIFICATION_EXPECTED,
                    message="L'alignement visuel d'un paragraphe semble non justifie.",
                    original=original,
                    proposed=original,
                    span=(start, start + len(original)) if start >= 0 else None,
                    page=page.page,
                    bbox=issue_line.bbox,
                )
            )
    return findings, checked_paragraphs, pages


def _evaluate_paragraph_justification(
    context: Any,
    _parameters: Mapping[str, Any],
) -> OperationResult:
    findings, checked_paragraphs, pages = _paragraph_justification_findings(context)
    if findings:
        return findings[0]

    if checked_paragraphs == 0:
        return OperationResult(
            status="INCONCLUSIVE",
            expected=_JUSTIFICATION_EXPECTED,
            page=pages[0].page if pages else None,
        )
    return OperationResult(
        status="PASS",
        expected=_JUSTIFICATION_EXPECTED,
        page=pages[-1].page,
    )


def _suggest_paragraph_justification(
    context: Any,
    _parameters: Mapping[str, Any],
) -> list[OperationResult]:
    findings, _checked_paragraphs, _pages = _paragraph_justification_findings(context)
    return findings


def revision_state(parsed: ParsedPdf, document: object) -> revision.RevisionState:
    """Build and cache revision state on the parsed document for this bundle run."""
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


def _findings(context: Any, parameters: Mapping[str, Any]) -> list[OperationResult]:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or parsed_pdf is None:
        return []
    control = parameters.get("control")
    if not isinstance(control, str) or not control:
        raise ValueError("revision_consistency operation requires control")

    state = revision_state(parsed_pdf, getattr(runtime, "document", None))
    targets = getattr(context, "targets", None)
    target_pages = (
        {target.raw_page for target in targets} if targets is not None else None
    )
    return [
        OperationResult(
            status="FAIL",
            observed=finding.original or finding.message,
            expected=finding.proposed or None,
            message=finding.message,
            original=finding.original,
            proposed=finding.proposed,
            page=finding.page,
            bbox=finding.bbox,
        )
        for finding in revision.findings_for(state, control)
        if target_pages is None or finding.page in target_pages
    ]


def _evaluate_revision_consistency(
    context: Any,
    parameters: Mapping[str, Any],
) -> OperationResult:
    control = parameters.get("control")
    if not isinstance(control, str) or not control:
        raise ValueError("revision_consistency operation requires control")
    runtime = getattr(context, "runtime", context)
    if getattr(runtime, "is_docx", False) or getattr(runtime, "parsed_pdf", None) is None:
        return OperationResult(status="INCONCLUSIVE", expected=control)

    findings = _findings(context, parameters)
    return findings[0] if findings else OperationResult(status="PASS", expected=control)


def _evaluate_shop_verification(
    context: Any,
    _parameters: Mapping[str, Any],
) -> OperationResult:
    runtime = getattr(context, "runtime", context)
    targets = getattr(context, "targets", ())
    expected = shop_verification_text(getattr(runtime, "document", None))
    first_failure: OperationResult | None = None
    for target in targets:
        observed = shop_verification_section(target.text)
        if shop_verification_matches(target.text, expected):
            continue
        if first_failure is None:
            first_failure = OperationResult(
                status="FAIL",
                observed=observed or None,
                expected=expected,
                original=observed,
                proposed=expected,
                message=(
                    "Shop Verification INTRODUCTION non conforme. "
                    f"Texte attendu pour {getattr(runtime.document, 'meta_manufacturer', 'Airbus')} : {expected}"
                ),
                page=target.raw_page,
            )
    if first_failure is not None:
        return first_failure
    page = targets[-1].raw_page if targets else None
    return OperationResult(status="PASS", observed=expected, expected=expected, page=page)


def _suggest_shop_verification(
    context: Any,
    _parameters: Mapping[str, Any],
) -> list[OperationResult]:
    runtime = getattr(context, "runtime", context)
    expected = shop_verification_text(getattr(runtime, "document", None))
    manufacturer = str(getattr(getattr(runtime, "document", None), "meta_manufacturer", "Airbus") or "Airbus")
    check = context.check
    failure_message = check and getattr(check, "failure_message", None)
    message_prefix = failure_message or "Shop Verification INTRODUCTION non conforme."
    results: list[OperationResult] = []
    for target in getattr(context, "targets", ()):
        if shop_verification_matches(target.text, expected):
            continue
        observed = shop_verification_section(target.text).strip()
        start = target.text.find(observed) if observed else target.text.lower().find("shop verification")
        if start < 0:
            start = 0
        results.append(
            OperationResult(
                status="FAIL",
                observed=observed or None,
                expected=expected,
                message=f"{message_prefix} Texte attendu pour {manufacturer} : {expected}",
                original=observed,
                proposed=expected,
                span=(start, start + len(observed)),
                page=target.raw_page,
                bbox_strategy="text" if observed else "empty_middle",
            )
        )
    return results


def _evaluate_highlights_holder(
    context: Any,
    _parameters: Mapping[str, Any],
) -> OperationResult:
    runtime = getattr(context, "runtime", context)
    targets = getattr(context, "targets", ())
    expected = highlights_holder_expected(getattr(runtime, "parsed_pdf", None))
    if expected is None:
        return OperationResult(status="INCONCLUSIVE")
    for target in targets:
        if highlights_holder_matches(target.text, expected):
            continue
        observed = highlights_holder_observed(target.text)
        return OperationResult(
            status="FAIL",
            observed=observed or None,
            expected=expected,
            original=observed,
            proposed=expected,
            message=(
                "La phrase TO: HOLDER OF des Highlights ne correspond pas au titre TP1. "
                f"Le contenu doit commencer par « {expected} »."
            ),
            page=target.raw_page,
        )
    page = targets[-1].raw_page if targets else None
    return OperationResult(status="PASS", observed=expected, expected=expected, page=page)


def _suggest_highlights_holder(
    context: Any,
    _parameters: Mapping[str, Any],
) -> list[OperationResult]:
    runtime = getattr(context, "runtime", context)
    expected = highlights_holder_expected(getattr(runtime, "parsed_pdf", None))
    if expected is None:
        return []
    check = context.check
    message_prefix = getattr(check, "failure_message", None) or (
        "La phrase TO: HOLDER OF des Highlights ne correspond pas au titre TP1."
    )
    results: list[OperationResult] = []
    for target in getattr(context, "targets", ()):
        if highlights_holder_matches(target.text, expected):
            continue
        original = highlights_holder_observed(target.text)
        start = target.text.find(original) if original else 0
        results.append(
            OperationResult(
                status="FAIL",
                observed=original or None,
                expected=expected,
                message=f"{message_prefix} Le contenu doit commencer par « {expected} ».",
                original=original,
                proposed=expected,
                span=(start, start + len(original)),
                page=target.raw_page,
                bbox_strategy="text" if original else "highlight_holder",
            )
        )
    return results


def _evaluate_highlights_document_type(
    context: Any,
    _parameters: Mapping[str, Any],
) -> OperationResult:
    targets = getattr(context, "targets", ())
    expected_options = " / ".join(DOCUMENT_TYPES)
    for target in targets:
        if highlights_document_type_matches(target.text):
            continue
        observed = highlights_document_type_observed(target.text)
        expected = highlights_document_type_expected(target.text) or expected_options
        return OperationResult(
            status="FAIL",
            observed=observed or None,
            expected=expected,
            original=observed,
            proposed=expected,
            message=(
                "Le type de document est absent au-dessus du numero ATA Highlights. "
                f"Texte attendu : {expected}."
            ),
            page=target.raw_page,
        )
    page = targets[-1].raw_page if targets else None
    return OperationResult(
        status="PASS",
        observed=expected_options,
        expected=expected_options,
        page=page,
    )


def _suggest_highlights_document_type(
    context: Any,
    _parameters: Mapping[str, Any],
) -> list[OperationResult]:
    check = context.check
    message_prefix = getattr(check, "failure_message", None) or (
        "type de document absent au-dessus du numero ATA Highlights."
    )
    results: list[OperationResult] = []
    for target in getattr(context, "targets", ()):
        if highlights_document_type_matches(target.text):
            continue
        expected = highlights_document_type_expected(target.text)
        if expected is None:
            continue
        original = highlights_document_type_observed(target.text)
        start = target.text.find(original) if original else 0
        results.append(
            OperationResult(
                status="FAIL",
                observed=original or None,
                expected=expected,
                message=f"{message_prefix} Texte attendu : {expected}.",
                original=original,
                proposed=expected,
                span=(start, start + len(original)),
                page=target.raw_page,
                bbox_strategy="text" if original else "missing_anchor",
            )
        )
    return results


def _chapter_heading(line: PdfLine) -> tuple[int, str] | None:
    match = _CHAPTER_HEADING_RE.match(line.text)
    if match is None:
        return None
    title = match.group("title").strip()
    words = re.findall(r"[^\W_]+", title)
    title_case = bool(words) and all(
        word[0].isupper() or word.casefold() in _CHAPTER_TITLE_CONNECTORS
        for word in words
    )
    if not title or title[-1] in ".!?;:" or not (title.isupper() or title_case):
        return None
    return int(match.group("number")), title


def _complete_pdf_pages(parsed_pdf: ParsedPdf) -> list[ParsedPage]:
    return (
        parsed_pdf.full_document_pages
        if parsed_pdf.full_document_pages is not None
        else parsed_pdf.pages
    )


def _ni_part_number_sort_key(value: str) -> tuple[int, str]:
    normalized = re.sub(r"[\u2010-\u2015\u2212]", "-", value.strip().casefold())
    first_character = next((character for character in normalized if character.isalnum()), "")
    prefix_group = 0 if first_character.isalpha() else 1
    return prefix_group, normalized


def _chapter_sequence_findings(
    context: Any,
) -> tuple[list[OperationResult], int]:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed_pdf, ParsedPdf):
        return [], 0
    document_pages = _complete_pdf_pages(parsed_pdf)
    if (
        not document_pages
        or document_pages[0].page != 1
        or document_pages[-1].page != len(document_pages)
    ):
        return [], 0

    targets = tuple(getattr(context, "targets", ()))
    target_pages = {target.raw_page for target in targets}
    if not target_pages:
        return [], 0
    text_by_page = {target.raw_page: target.text for target in targets}
    headings_by_chapter: dict[
        str, list[tuple[int, ParsedPage, PdfLine, str]]
    ] = defaultdict(list)
    for page in document_pages:
        page_text = page.text or ""
        if (
            _TABLE_OF_CONTENTS_MARKER.search(page_text)
            or revision._is_highlights_page(page)
            or revision._is_lep_page(page)
            or revision._is_ror_page(page)
            or page.page_type in {"TP1", "TP2", "HIGHLIGHTS", "HIGHLIGHTS_PAGE_1"}
        ):
            continue
        footer = revision.extract_footer(page)
        page_key = footer.page_key if footer is not None else None
        if page_key is None or re.fullmatch(r"\d{3,4}", page_key) is None:
            continue
        chapter = page_key[:-2]
        for line in sorted(page.lines, key=lambda item: (item.bbox[1], item.bbox[0])):
            heading = _chapter_heading(line)
            if heading is None:
                continue
            number, title = heading
            headings_by_chapter[chapter].append((number, page, line, title))

    findings: list[OperationResult] = []
    candidate_count = 0
    for chapter, headings in headings_by_chapter.items():
        expected_number = 1
        for number, page, line, title in headings:
            candidate_count += 1
            if number == expected_number:
                expected_number += 1
                continue
            if page.page not in target_pages:
                if number > expected_number:
                    expected_number = number + 1
                continue
            original = line.text.strip()
            start = text_by_page.get(page.page, "").find(original)
            findings.append(
                OperationResult(
                    status="FAIL",
                    observed=original,
                    expected=f"{expected_number}. {title}",
                    message=(
                        f"Ordre des chapitres incoherent dans la serie {chapter}: "
                        f"numero attendu {expected_number}, trouve {number}."
                    ),
                    original=original,
                    proposed=f"{expected_number}. {title}",
                    span=(start, start + len(original)) if start >= 0 else None,
                    page=page.page,
                    bbox=line.bbox,
                )
            )
            if number > expected_number:
                expected_number = number + 1
    return findings, candidate_count


def _highlights_description_findings(
    context: Any,
    control: str,
) -> tuple[list[OperationResult], int]:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed_pdf, ParsedPdf):
        return [], 0
    targets = tuple(getattr(context, "targets", ()))
    target_pages = {target.raw_page for target in targets}
    text_by_page = {target.raw_page: target.text for target in targets}
    entries = [
        entry
        for page in parsed_pdf.pages
        if not target_pages or page.page in target_pages
        for entry in revision.extract_highlights(page)
    ]
    if not entries:
        return [], 0

    findings: list[OperationResult] = []
    reported_illustrated_lists: set[tuple[int, str]] = set()
    for entry in entries:
        if control == "highlights_deleted_description":
            if entry.status != "D" or _DELETED_DESCRIPTION_RE.search(entry.description):
                continue
            expected = "Chapter deleted ou Page deleted"
            message = (
                f"La ligne D « {entry.pages_text} » doit avoir la description "
                "« Chapter deleted » ou « Page deleted » en face."
            )
            original = entry.description
            bbox = entry.description_bbox
        elif control == "highlights_revised_description":
            if entry.status != "R":
                continue
            illustrated_parts_list = bool(
                _ILLUSTRATED_PARTS_LIST_RE.search(entry.subject)
            )
            description = (
                entry.description
                or (entry.subject_description if illustrated_parts_list else "")
            )
            if any(character.isalnum() for character in description):
                continue
            if illustrated_parts_list:
                group_key = (entry.page, entry.subject.casefold())
                if group_key in reported_illustrated_lists:
                    continue
                reported_illustrated_lists.add(group_key)
                expected = "Description de changement sur la ligne Illustrated Parts List"
                message = (
                    "Les lignes R de l'Illustrated Parts List peuvent rester sans "
                    "description si celle-ci figure en face de leur rubrique."
                )
                bbox = entry.subject_description_bbox or entry.description_bbox
            else:
                expected = "Description of Change"
                message = (
                    f"La ligne R « {entry.pages_text} » doit avoir une description "
                    "dans la colonne Description of Change."
                )
                bbox = entry.description_bbox
            original = entry.description
        else:
            raise ValueError(f"unknown document_structure control: {control}")

        start = text_by_page.get(entry.page, "").find(original) if original else -1
        findings.append(
            OperationResult(
                status="FAIL",
                observed=original or None,
                expected=expected,
                message=message,
                original=original,
                proposed=expected,
                span=(start, start + len(original)) if start >= 0 else (0, 0),
                page=entry.page,
                bbox=bbox,
            )
        )
    return findings, len(entries)


def _list_materials_code_findings(
    context: Any,
) -> tuple[list[OperationResult], int]:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed_pdf, ParsedPdf):
        return [], 0

    targets = tuple(getattr(context, "targets", ()))
    target_pages = {target.raw_page for target in targets}
    text_by_page = {target.raw_page: target.text for target in targets}
    findings: list[OperationResult] = []
    checked_pages = 0
    for page in parsed_pdf.pages:
        if target_pages and page.page not in target_pages:
            continue
        footer = revision.extract_footer(page)
        if (
            footer is None
            or revision.page_key_prefix(footer.page_key).casefold() != "lm"
            or _LIST_OF_MATERIALS_TITLE_RE.search(page.text or "") is None
        ):
            continue

        designation_header = next(
            (span for span in page.spans if span.text.strip().upper() == "DESIGNATION"),
            None,
        )
        code_header = next(
            (span for span in page.spans if span.text.strip().upper() == "CODE"),
            None,
        )
        suppliers_header = next(
            (span for span in page.spans if _SUPPLIERS_HEADER_RE.match(span.text.strip())),
            None,
        )
        if designation_header is None or code_header is None or suppliers_header is None:
            continue

        designation_center = (designation_header.bbox[0] + designation_header.bbox[2]) / 2
        code_center = (code_header.bbox[0] + code_header.bbox[2]) / 2
        suppliers_center = (suppliers_header.bbox[0] + suppliers_header.bbox[2]) / 2
        column_left = (designation_center + code_center) / 2
        column_right = (code_center + suppliers_center) / 2
        header_bottom = max(
            designation_header.bbox[3],
            code_header.bbox[3],
            suppliers_header.bbox[3],
        )
        designation_data = [
            span
            for span in page.spans
            if (span.bbox[0] + span.bbox[2]) / 2 < column_left
            and span.bbox[1] > header_bottom
            and span.text.strip()
        ]
        if not designation_data:
            continue
        first_data_top = min(span.bbox[1] for span in designation_data)
        checked_pages += 1

        for row in revision.visual_rows(page.spans):
            if min(span.bbox[1] for span in row) < first_data_top - 3.0:
                continue
            for span in row:
                center_x = (span.bbox[0] + span.bbox[2]) / 2
                if (
                    not column_left <= center_x < column_right
                    or not any(character in span.text for character in "()")
                ):
                    continue
                original = span.text.strip()
                start = text_by_page.get(page.page, "").find(original)
                findings.append(
                    OperationResult(
                        status="FAIL",
                        observed=original,
                        expected="Code sans parentheses",
                        message=(
                            f"Le code « {original} » de la page LM doit etre ecrit "
                            "sans parentheses."
                        ),
                        original=original,
                        proposed=original.replace("(", "").replace(")", ""),
                        span=(start, start + len(original)) if start >= 0 else None,
                        page=page.page,
                        bbox=span.bbox,
                    )
                )
    return findings, checked_pages


def _numerical_index_order_findings(
    context: Any,
) -> tuple[list[OperationResult], int]:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed_pdf, ParsedPdf):
        return [], 0
    document_pages = _complete_pdf_pages(parsed_pdf)
    if (
        not document_pages
        or document_pages[0].page != 1
        or document_pages[-1].page != len(document_pages)
    ):
        return [], 0

    targets = tuple(getattr(context, "targets", ()))
    target_pages = {target.raw_page for target in targets}
    if not target_pages:
        return [], 0
    text_by_page = {target.raw_page: target.text for target in targets}
    index_pages: list[tuple[str, int, ParsedPage, float]] = []
    for page in document_pages:
        footer = revision.extract_footer(page)
        if footer is None or footer.page_key is None:
            continue
        page_match = _NUMERICAL_INDEX_PAGE_RE.fullmatch(footer.page_key)
        if page_match is None:
            continue
        part_headers = [
            span
            for span in page.spans
            if span.text.strip().upper() == "PART NUMBER"
        ]
        if not part_headers:
            continue
        part_header = min(part_headers, key=lambda span: span.bbox[0])
        header_center = (part_header.bbox[1] + part_header.bbox[3]) / 2
        part_center_x = (part_header.bbox[0] + part_header.bbox[2]) / 2
        following_headers = [
            span
            for span in page.spans
            if (
                (span.bbox[0] + span.bbox[2]) / 2 > part_center_x + 5.0
                and abs((span.bbox[1] + span.bbox[3]) / 2 - header_center) <= 50.0
                and (
                    span.text.strip().upper() in _NI_HEADER_LABELS
                    or span.text.strip().upper().startswith("CH-SECT")
                )
            )
        ]
        if not following_headers:
            continue
        next_header = min(
            following_headers,
            key=lambda span: (span.bbox[0] + span.bbox[2]) / 2,
        )
        next_center_x = (next_header.bbox[0] + next_header.bbox[2]) / 2
        column_right = (part_center_x + next_center_x) / 2

        header_spans = [
            span
            for span in page.spans
            if (
                abs((span.bbox[1] + span.bbox[3]) / 2 - header_center) <= 60.0
                and (
                    span.text.strip().upper() in _NI_HEADER_LABELS
                    or span.text.strip().upper().startswith("CH-SECT")
                )
            )
        ]
        header_bottom = max(span.bbox[3] for span in [part_header, *header_spans])
        index_pages.append(
            (
                page_match.group("manual").casefold(),
                int(page_match.group("page")),
                page,
                column_right,
            )
        )

    checked_numbers = 0
    part_numbers_by_manual: dict[
        str,
        list[
            tuple[
                str,
                tuple[int, str],
                ParsedPage,
                tuple[float, float, float, float],
            ]
        ],
    ] = defaultdict(list)
    for manual, _ordinal, page, column_right in sorted(
        index_pages, key=lambda item: (item[0], item[1])
    ):
        part_headers = [
            span
            for span in page.spans
            if span.text.strip().upper() == "PART NUMBER"
        ]
        if not part_headers:
            continue
        part_header = min(part_headers, key=lambda span: span.bbox[0])
        header_center = (part_header.bbox[1] + part_header.bbox[3]) / 2
        header_spans = [
            span
            for span in page.spans
            if (
                abs((span.bbox[1] + span.bbox[3]) / 2 - header_center) <= 60.0
                and (
                    span.text.strip().upper() in _NI_HEADER_LABELS
                    or span.text.strip().upper().startswith("CH-SECT")
                )
            )
        ]
        header_bottom = max(span.bbox[3] for span in [part_header, *header_spans])
        for row in revision.visual_rows(page.spans):
            if (
                min(span.bbox[1] for span in row) <= header_bottom
                or (
                    page.page_height > 0
                    and max(span.bbox[3] for span in row) > page.page_height * 0.94
                )
            ):
                continue
            part_spans = [
                span
                for span in row
                if (span.bbox[0] + span.bbox[2]) / 2 < column_right
            ]
            part_number = "".join(span.text.strip() for span in part_spans)
            if not any(character.isalnum() for character in part_number):
                continue
            part_number_key = _ni_part_number_sort_key(part_number)
            checked_numbers += 1
            bbox = (
                min(span.bbox[0] for span in part_spans),
                min(span.bbox[1] for span in part_spans),
                max(span.bbox[2] for span in part_spans),
                max(span.bbox[3] for span in part_spans),
            )
            part_numbers_by_manual[manual].append(
                (part_number, part_number_key, page, bbox)
            )

    findings: list[OperationResult] = []
    for manual, entries in part_numbers_by_manual.items():
        sequence_lengths = [1] * len(entries)
        predecessors = [-1] * len(entries)
        for index, (_part_number, part_number_key, _page, _bbox) in enumerate(entries):
            for previous_index in range(index):
                if (
                    entries[previous_index][1] <= part_number_key
                    and sequence_lengths[previous_index] + 1 > sequence_lengths[index]
                ):
                    sequence_lengths[index] = sequence_lengths[previous_index] + 1
                    predecessors[index] = previous_index

        in_order: set[int] = set()
        index = (
            max(range(len(sequence_lengths)), key=sequence_lengths.__getitem__)
            if sequence_lengths
            else -1
        )
        while index >= 0:
            in_order.add(index)
            index = predecessors[index]

        for index, (part_number, _key, page, bbox) in enumerate(entries):
            if index in in_order or page.page not in target_pages:
                continue
            start = text_by_page.get(page.page, "").find(part_number)
            findings.append(
                OperationResult(
                    status="FAIL",
                    observed=part_number,
                    expected="Part Number en ordre alphanumerique croissant",
                    message=(
                        f"Le Part Number « {part_number} » de la page NI/NUM "
                        f"{manual} est hors de la sous-sequence alphanumerique "
                        "croissante et doit etre repositionne."
                    ),
                    original=part_number,
                    proposed="",
                    span=(start, start + len(part_number)) if start >= 0 else None,
                    page=page.page,
                    bbox=bbox,
                )
            )
    return findings, checked_numbers


def _document_structure_findings(
    context: Any,
    parameters: Mapping[str, Any],
) -> tuple[list[OperationResult], int, str]:
    control = parameters.get("control")
    if control == "chapter_sequence":
        findings, checked = _chapter_sequence_findings(context)
        expected = "Chapitres numerotes dans l'ordre 1, 2, 3..."
    elif control in {
        "highlights_deleted_description",
        "highlights_revised_description",
    }:
        findings, checked = _highlights_description_findings(context, control)
        expected = (
            "Chapter deleted ou Page deleted"
            if control == "highlights_deleted_description"
            else "Une description de modification"
        )
    elif control == "list_materials_code_parentheses":
        findings, checked = _list_materials_code_findings(context)
        expected = "Code de la LIST OF MATERIALS sans parentheses"
    elif control == "ni_part_number_order":
        findings, checked = _numerical_index_order_findings(context)
        expected = "Part Number numeriques en ordre croissant"
    else:
        raise ValueError(f"unknown document_structure control: {control}")
    return findings, checked, expected


def _evaluate_document_structure(
    context: Any,
    parameters: Mapping[str, Any],
) -> OperationResult:
    findings, checked, expected = _document_structure_findings(context, parameters)
    if findings:
        return findings[0]
    if checked == 0:
        return OperationResult(status="INCONCLUSIVE", expected=expected)
    targets = getattr(context, "targets", ())
    return OperationResult(
        status="PASS",
        expected=expected,
        page=targets[-1].raw_page if targets else None,
    )


def _suggest_document_structure(
    context: Any,
    parameters: Mapping[str, Any],
) -> list[OperationResult]:
    findings, _checked, _expected = _document_structure_findings(context, parameters)
    return findings


def _evaluate_highlights_legend_footer(
    context: Any,
    _parameters: Mapping[str, Any],
) -> OperationResult:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed_pdf, ParsedPdf):
        return OperationResult(
            status="INCONCLUSIVE",
            expected=_HIGHLIGHTS_LEGEND_FOOTER_EXPECTED,
        )

    target_pages = {target.raw_page for target in getattr(context, "targets", ())}
    pages = [page for page in parsed_pdf.pages if page.page in target_pages]
    if not pages:
        return OperationResult(
            status="INCONCLUSIVE",
            expected=_HIGHLIGHTS_LEGEND_FOOTER_EXPECTED,
        )

    for page in pages:
        lines = _highlights_visual_lines(page)
        footer_start = _highlights_footer_start(lines)
        if footer_start is None:
            return OperationResult(
                status="INCONCLUSIVE",
                expected=_HIGHLIGHTS_LEGEND_FOOTER_EXPECTED,
                page=page.page,
            )

        legends = [
            line
            for line in lines
            if _HIGHLIGHTS_LEGEND_RE.search(line[0])
            and (line[1][1] + line[1][3]) / 2 < footer_start
        ]
        if not legends:
            return OperationResult(
                status="FAIL",
                expected=_HIGHLIGHTS_LEGEND_FOOTER_EXPECTED,
                message=(
                    "La legende du tableau Highlights est absente au-dessus du "
                    "pied de page."
                ),
                page=page.page,
            )

        legend = max(legends, key=lambda item: (item[1][1] + item[1][3]) / 2)
        legend_center = (legend[1][1] + legend[1][3]) / 2
        intervening_lines = [
            line
            for line in lines
            if legend_center < (line[1][1] + line[1][3]) / 2 < footer_start
        ]
        if intervening_lines:
            issue_text, issue_bbox = min(
                intervening_lines,
                key=lambda item: (item[1][1] + item[1][3]) / 2,
            )
            return OperationResult(
                status="FAIL",
                observed=issue_text,
                expected=_HIGHLIGHTS_LEGEND_FOOTER_EXPECTED,
                message=(
                    "Une ligne de texte s'intercale entre la legende du tableau "
                    "Highlights et le pied de page."
                ),
                original=issue_text,
                page=page.page,
                bbox=issue_bbox,
            )

    return OperationResult(
        status="PASS",
        expected=_HIGHLIGHTS_LEGEND_FOOTER_EXPECTED,
        page=pages[-1].page,
    )


def _evaluate_copyright_position(
    context: Any,
    _parameters: Mapping[str, Any],
) -> OperationResult:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed_pdf, ParsedPdf):
        return OperationResult(
            status="INCONCLUSIVE",
            expected=_COPYRIGHT_POSITION_EXPECTED,
        )

    target_pages = {target.raw_page for target in getattr(context, "targets", ())}
    pages = [page for page in parsed_pdf.pages if page.page in target_pages]
    if not pages:
        return OperationResult(
            status="INCONCLUSIVE",
            expected=_COPYRIGHT_POSITION_EXPECTED,
        )

    inconclusive_pages: list[int] = []
    for page in pages:
        expected_x_cm = (
            _COPYRIGHT_POSITION_ODD_X_CM
            if page.page % 2
            else _COPYRIGHT_POSITION_EVEN_X_CM
        )
        parity = "impaire" if page.page % 2 else "paire"
        expected = (
            f"page {page.page} ({parity}): x={expected_x_cm:.2f} cm, "
            f"y={_COPYRIGHT_POSITION_Y_CM:.2f} cm "
            f"(+/- {_COPYRIGHT_POSITION_TOLERANCE_CM:.2f} cm)"
        )
        copyright_spans = [
            span
            for span in page.spans
            if _COPYRIGHT_POSITION_MARKER_RE.search(span.text)
        ]
        if not copyright_spans:
            if not page.has_text_layer:
                inconclusive_pages.append(page.page)
                continue
            return OperationResult(
                status="FAIL",
                expected=expected,
                message=f"Le copyright est absent de la page PDF {page.page}.",
                page=page.page,
            )

        copyright_span = min(
            copyright_spans,
            key=lambda span: (span.bbox[1], span.bbox[0]),
        )
        observed_x_cm = copyright_span.bbox[0] / _POINTS_PER_CENTIMETER
        observed_y_cm = copyright_span.bbox[1] / _POINTS_PER_CENTIMETER
        if (
            abs(observed_x_cm - expected_x_cm) > _COPYRIGHT_POSITION_TOLERANCE_CM
            or abs(observed_y_cm - _COPYRIGHT_POSITION_Y_CM)
            > _COPYRIGHT_POSITION_TOLERANCE_CM
        ):
            observed = f"x={observed_x_cm:.2f} cm, y={observed_y_cm:.2f} cm"
            return OperationResult(
                status="FAIL",
                observed=observed,
                expected=expected,
                message=(
                    f"Le copyright de la page {page.page} est en {observed}; "
                    f"position attendue : {expected}."
                ),
                original=copyright_span.text,
                page=page.page,
                bbox=copyright_span.bbox,
            )

    if inconclusive_pages:
        return OperationResult(
            status="INCONCLUSIVE",
            expected=_COPYRIGHT_POSITION_EXPECTED,
            page=inconclusive_pages[0],
            inconclusive_pages=inconclusive_pages,
        )
    return OperationResult(
        status="PASS",
        expected=_COPYRIGHT_POSITION_EXPECTED,
        page=pages[-1].page,
    )


REVISION_CONSISTENCY = ClientOperation(
    name="revision_consistency",
    execute=_evaluate_revision_consistency,
    suggestions=_findings,
)
SHOP_VERIFICATION = ClientOperation(
    name="shop_verification",
    execute=_evaluate_shop_verification,
    suggestions=_suggest_shop_verification,
)
HIGHLIGHTS_HOLDER = ClientOperation(
    name="highlights_holder",
    execute=_evaluate_highlights_holder,
    suggestions=_suggest_highlights_holder,
)
HIGHLIGHTS_DOCUMENT_TYPE = ClientOperation(
    name="highlights_document_type",
    execute=_evaluate_highlights_document_type,
    suggestions=_suggest_highlights_document_type,
)
PARAGRAPH_JUSTIFICATION = ClientOperation(
    name="paragraph_justification",
    execute=_evaluate_paragraph_justification,
    suggestions=_suggest_paragraph_justification,
)
HIGHLIGHTS_LEGEND_FOOTER = ClientOperation(
    name="highlights_legend_footer",
    execute=_evaluate_highlights_legend_footer,
)
COPYRIGHT_POSITION = ClientOperation(
    name="copyright_position",
    execute=_evaluate_copyright_position,
)
DOCUMENT_STRUCTURE = ClientOperation(
    name="document_structure",
    execute=_evaluate_document_structure,
    suggestions=_suggest_document_structure,
)
OPERATIONS = {
    operation.name: operation
    for operation in (
        REVISION_CONSISTENCY,
        SHOP_VERIFICATION,
        HIGHLIGHTS_HOLDER,
        HIGHLIGHTS_DOCUMENT_TYPE,
        PARAGRAPH_JUSTIFICATION,
        HIGHLIGHTS_LEGEND_FOOTER,
        COPYRIGHT_POSITION,
        DOCUMENT_STRUCTURE,
    )
}
