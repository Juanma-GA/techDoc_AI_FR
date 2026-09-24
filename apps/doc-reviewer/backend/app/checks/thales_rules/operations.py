"""THALES operations registered through the generic client-operation contract."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.checks.client_bundle import ClientOperation, OperationResult
from . import revision_engine as revision
from .rules import (
    DOCUMENT_TYPE_PATTERN,
    DOCUMENT_TYPES,
    HIGHLIGHTS_DOCUMENT_TYPE_PATTERN,
)
from app.core.logging import get_logger
from app.parsers.pdf_parser import ParsedPdf


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
OPERATIONS = {
    operation.name: operation
    for operation in (
        REVISION_CONSISTENCY,
        SHOP_VERIFICATION,
        HIGHLIGHTS_HOLDER,
        HIGHLIGHTS_DOCUMENT_TYPE,
    )
}
