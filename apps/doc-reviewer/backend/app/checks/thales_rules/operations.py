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
_JUSTIFICATION_EXPECTED = "visuellement justifie a gauche et a droite, hors derniere ligne"
_JUSTIFICATION_MIN_LINE_CHARACTERS = 24
_JUSTIFICATION_HORIZONTAL_TOLERANCE = 3.0


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
    content = highlights_content(text)
    first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
    return first_line if _HIGHLIGHTS_HOLDER_RE.match(first_line) else ""


def highlights_holder_matches(text: str, expected: str) -> bool:
    observed = " ".join(highlights_content(text).split()).casefold()
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
        current: list[PdfLine] = []
        for line in sorted(block_lines, key=lambda item: item.line_index):
            if current:
                previous = current[-1]
                line_height = max(
                    previous.bbox[3] - previous.bbox[1],
                    line.bbox[3] - line.bbox[1],
                    1.0,
                )
                if line.bbox[1] - previous.bbox[1] > max(18.0, line_height * 1.8):
                    paragraphs.append(current)
                    current = []
            current.append(line)
        if current:
            paragraphs.append(current)
    return paragraphs


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
    target_pages = {target.raw_page for target in targets}
    pages = [page for page in parsed_pdf.pages if page.page in target_pages]
    text_by_page = {target.raw_page: target.text for target in targets}
    checked_paragraphs = 0
    findings: list[OperationResult] = []
    for page in pages:
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
OPERATIONS = {
    operation.name: operation
    for operation in (
        REVISION_CONSISTENCY,
        SHOP_VERIFICATION,
        HIGHLIGHTS_HOLDER,
        HIGHLIGHTS_DOCUMENT_TYPE,
        PARAGRAPH_JUSTIFICATION,
    )
}
