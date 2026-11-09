"""Manufacturer-specific THALES storage-note checks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from app.checks.client_bundle import ClientOperation, OperationResult


StorageReference = Literal["relative_humidity", "temperature"]
_STORAGE_REFERENCES: dict[StorageReference, dict[str, str]] = {
    "relative_humidity": {
        "airbus": (
            "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00, "
            "F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
        ),
        "boeing": (
            "Relative humidity: Refer to SOPM 20-02-00 - STANDARD OVERHAUL PRACTICES "
            "MANUAL (SOPM), F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
        ),
    },
    "temperature": {
        "airbus": (
            "Temperature: Refer to Standard Practices Manual ATA No. 20-02-00, "
            "F9111CMON-A-20-02-00-00A-812A-A – Storage and Transportation of Assemblies."
        ),
        "boeing": (
            "Temperature: Refer to SOPM 20-02-00 - STANDARD OVERHAUL PRACTICES MANUAL "
            "(SOPM), F9111CMON-A-20-02-00-00A-812A-A - Storage and Transportation of Assemblies."
        ),
    },
}
_REFERENCE_LABELS: dict[StorageReference, str] = {
    "relative_humidity": "Relative humidity",
    "temperature": "Temperature",
}
_STORAGE_NOTE_INTRODUCTION = (
    "During storage operations, make sure that the environmental conditions "
    "are as follows:"
)
_STORAGE_NOTE_INTRODUCTION_RE = re.compile(
    r"(?i:\bNOTE\b)\s*:\s*"
    + re.escape(_STORAGE_NOTE_INTRODUCTION).replace(r"\ ", r"\s+")
)
_NEXT_NOTE_RE = re.compile(r"(?i)\bNOTE\b")
_DASH_PATTERN = r"[-\u2010-\u2015\u2212\uFFFD]"


def _storage_reference(reference: Any) -> StorageReference:
    if reference == "relative_humidity":
        return "relative_humidity"
    if reference == "temperature":
        return "temperature"
    raise ValueError(f"Unsupported storage reference: {reference!r}")


def _storage_reference_text(
    document: object | None,
    reference: StorageReference,
) -> str:
    manufacturer = str(getattr(document, "meta_manufacturer", "Airbus") or "Airbus")
    manufacturer_key = (
        "boeing" if manufacturer.strip().casefold() == "boeing" else "airbus"
    )
    return _STORAGE_REFERENCES[reference][manufacturer_key]


def _storage_note_body(text: str) -> tuple[int, int] | None:
    introduction = _STORAGE_NOTE_INTRODUCTION_RE.search(text)
    if introduction is None:
        return None
    next_note = _NEXT_NOTE_RE.search(text, introduction.end())
    return (
        introduction.end(),
        next_note.start() if next_note is not None else len(text),
    )


def _reference_pattern(
    expected: str,
    reference: StorageReference,
) -> re.Pattern[str]:
    escaped = re.escape(expected).replace(r"\ ", r"\s+")
    escaped = (
        escaped.replace(r"CMON\-A", rf"CMON\s*{_DASH_PATTERN}?\s*A")
        .replace(r"\-", _DASH_PATTERN)
        .replace(r"\–", _DASH_PATTERN)
        .replace("–", _DASH_PATTERN)
    )
    if reference == "relative_humidity":
        escaped = escaped.replace(
            "procedure",
            r"proc(?:e|\u00e9|\uFFFD)dure",
        )
    return re.compile(escaped, re.IGNORECASE)


def _reference_line_pattern(reference: StorageReference) -> re.Pattern[str]:
    label = re.escape(_REFERENCE_LABELS[reference])
    return re.compile(rf"(?im)^[ \t]*{label}\s*:[^\r\n]*")


def _has_expected_reference(
    text: str,
    expected: str,
    reference: StorageReference,
) -> bool:
    body = _storage_note_body(text)
    if body is None:
        return False
    return (
        _reference_pattern(expected, reference).search(text, body[0], body[1])
        is not None
    )


def _evaluate_storage_note_reference(
    context: Any,
    parameters: Mapping[str, Any],
) -> OperationResult:
    reference = _storage_reference(parameters.get("reference"))
    runtime = getattr(context, "runtime", context)
    targets = getattr(context, "targets", ())
    expected = _storage_reference_text(getattr(runtime, "document", None), reference)
    label = _REFERENCE_LABELS[reference]
    for target in targets:
        if _has_expected_reference(target.text, expected, reference):
            continue
        body = _storage_note_body(target.text)
        reference_line = (
            _reference_line_pattern(reference).search(target.text, body[0], body[1])
            if body is not None
            else None
        )
        observed = reference_line.group(0) if reference_line is not None else ""
        return OperationResult(
            status="FAIL",
            observed=observed or None,
            expected=expected,
            message=f"Reference {label} STORAGE non conforme. Texte attendu : {expected}",
            original=observed,
            proposed=expected,
            span=reference_line.span() if reference_line is not None else None,
            page=target.raw_page,
        )
    page = targets[-1].raw_page if targets else None
    return OperationResult(status="PASS", expected=expected, page=page)


def _missing_reference_insertion(
    text: str,
    body: tuple[int, int],
    check: Any,
) -> int:
    anchor_pattern = getattr(check, "missing_anchor", None)
    if not isinstance(anchor_pattern, str) or not anchor_pattern:
        return body[1]
    anchor = re.compile(anchor_pattern).search(text, body[0], body[1])
    if anchor is None:
        return body[1]
    insertion = anchor.start() if check.missing_anchor_position == "above" else anchor.end()
    if check.missing_anchor_position == "below":
        newline = text.find("\n", insertion, body[1])
        if newline >= 0:
            insertion = newline + 1
    return insertion


def _suggest_storage_note_reference(
    context: Any,
    parameters: Mapping[str, Any],
) -> list[OperationResult]:
    reference = _storage_reference(parameters.get("reference"))
    runtime = getattr(context, "runtime", context)
    expected = _storage_reference_text(getattr(runtime, "document", None), reference)
    label = _REFERENCE_LABELS[reference]
    check = getattr(context, "check", None)
    message_prefix = getattr(check, "failure_message", None) or (
        f"Reference {label} STORAGE non conforme."
    )
    results: list[OperationResult] = []
    for target in getattr(context, "targets", ()):
        if _has_expected_reference(target.text, expected, reference):
            continue
        body = _storage_note_body(target.text)
        if body is None:
            continue
        reference_line = _reference_line_pattern(reference).search(
            target.text, body[0], body[1]
        )
        if reference_line is not None:
            original = reference_line.group(0)
            span = reference_line.span()
            bbox_strategy = "text"
        else:
            original = ""
            insertion = _missing_reference_insertion(target.text, body, check)
            span = (insertion, insertion)
            bbox_strategy = "missing_anchor"
        results.append(
            OperationResult(
                status="FAIL",
                expected=expected,
                message=f"{message_prefix} Texte attendu : {expected}.",
                original=original,
                proposed=expected,
                span=span,
                page=target.raw_page,
                bbox_strategy=bbox_strategy,
            )
        )
    return results


STORAGE_NOTE_REFERENCE = ClientOperation(
    name="storage_note_reference",
    execute=_evaluate_storage_note_reference,
    suggestions=_suggest_storage_note_reference,
)
