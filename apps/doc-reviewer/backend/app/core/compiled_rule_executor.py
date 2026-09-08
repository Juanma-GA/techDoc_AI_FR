"""Deterministic execution for the strict CompiledRule vocabulary."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.checks.raw import RawSuggestion
from app.core.compiled_rules import (
    Check,
    CompiledRule,
    DocxEvidenceLocation,
    Evidence,
    PdfEvidenceLocation,
    RuleResult,
)
from app.parsers.docx_parser import Block
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


_ENTITY_PATTERNS = {
    "revision_number": re.compile(
        r"(?i)\b(?:rev(?:ision)?\s*(?:no\.?|number|n°)?\s*[:#-]?\s*)([^\n|]+)"
    ),
    "revision_date": re.compile(r"(?i)\brevision\s+date\s*[:#-]?\s*([^\n|]+)"),
    "first_issue_date": re.compile(r"(?i)\bfirst\s+issue\s+date\s*[:#-]?\s*([^\n|]+)"),
    "copyright_start_year": re.compile(r"(?i)(?:©|copyright)\s*(\d{4})"),
    "copyright_end_year": re.compile(r"(?i)(?:©|copyright)\s*\d{4}\s*[-–]\s*(\d{4})"),
}


@dataclass(frozen=True)
class _TextTarget:
    page: str
    text: str
    raw_page: int
    bbox: tuple[float, float, float, float] | None = None
    target_id: str | None = None


def execute_pdf_rules(parsed: ParsedPdf, rules: list[CompiledRule]) -> tuple[list[RuleResult], list[RawSuggestion]]:
    targets = [
        _TextTarget(page=str(page.page), text=page.text, raw_page=page.page)
        for page in parsed.pages
    ]
    return _execute(rules, targets, parsed.pages, is_docx=False)


def execute_docx_rules(blocks: list[Block], rules: list[CompiledRule]) -> tuple[list[RuleResult], list[RawSuggestion]]:
    targets = [
        _TextTarget(
            page=str(block.page),
            text=block.text,
            raw_page=block.index,
            target_id=block.target_id,
        )
        for block in blocks
    ]
    return _execute(rules, targets, None, is_docx=True, blocks=blocks)


def _execute(
    rules: list[CompiledRule],
    targets: list[_TextTarget],
    pdf_pages: list[ParsedPage] | None,
    *,
    is_docx: bool,
    blocks: list[Block] | None = None,
) -> tuple[list[RuleResult], list[RawSuggestion]]:
    results: list[RuleResult] = []
    raws: list[RawSuggestion] = []
    for rule in rules:
        if rule.execution != "deterministic":
            results.append(RuleResult(rule_id=rule.id, status=rule.execution.upper()))  # type: ignore[arg-type]
            continue
        scoped = _scope_targets(rule, targets, is_docx=is_docx, blocks=blocks)
        if scoped is None or not scoped:
            evidence = _evidence(targets[0] if targets else None, None, None, is_docx, pdf_pages)
            results.append(RuleResult(rule_id=rule.id, status="INCONCLUSIVE", evidence=evidence))
            continue
        result = _evaluate_rule(rule, scoped, is_docx, pdf_pages)
        results.append(result)
        if result.status == "FAIL" and result.evidence is not None:
            raw_page = next((target.raw_page for target in scoped if target.page == result.evidence.page), scoped[0].raw_page)
            raws.append(
                RawSuggestion(
                    rule_kind="compiled_standard" if rule.source == "standard_rule" else "compiled_checklist",
                    rule_code=rule.id,
                    severity="warning",
                    message=f"Règle compilée non satisfaite: {rule.topic}",
                    original=result.evidence.observed_value or "",
                    proposed=result.evidence.expected_value or "",
                    page=raw_page,
                    span=(0, len(result.evidence.observed_value or "")),
                )
            )
    return results, raws


def _scope_targets(
    rule: CompiledRule,
    targets: list[_TextTarget],
    *,
    is_docx: bool,
    blocks: list[Block] | None,
) -> list[_TextTarget] | None:
    scoped = targets if rule.target.page == "all" else [target for target in targets if target.page == rule.target.page]
    if rule.target.region == "full_page":
        return scoped
    if not is_docx or blocks is None:
        return None
    allowed_ids = {block.target_id for block in blocks if block.zone == rule.target.region}
    return [target for target in scoped if target.target_id in allowed_ids]


def _evaluate_rule(
    rule: CompiledRule,
    targets: list[_TextTarget],
    is_docx: bool,
    pdf_pages: list[ParsedPage] | None,
) -> RuleResult:
    for check in rule.checks:
        passed, target, observed = _evaluate_check(check, targets)
        if not passed:
            evidence = _evidence(target, observed, check.expected, is_docx, pdf_pages)
            return RuleResult(rule_id=rule.id, status="FAIL", evidence=evidence)
    check = rule.checks[-1]
    _passed, target, observed = _evaluate_check(check, targets)
    return RuleResult(
        rule_id=rule.id,
        status="PASS",
        evidence=_evidence(target, observed, check.expected, is_docx, pdf_pages),
    )


def _evaluate_check(check: Check, targets: list[_TextTarget]) -> tuple[bool, _TextTarget, str | None]:
    values = [(target, _field_value(check.field, target.text, target.page)) for target in targets]
    expected = None if check.expected is None else str(check.expected)
    if check.operator == "exists":
        match = next(((target, value) for target, value in values if value and (expected is None or expected in value)), None)
        return (match is not None, *(match or (targets[0], None)))
    if check.operator == "not_exists":
        match = next(((target, value) for target, value in values if value and (expected is None or expected in value)), None)
        return (match is None, *((targets[0], None) if match is None else match))
    if check.operator == "regex":
        if expected is None:
            return False, targets[0], None
        for target, value in values:
            match = re.search(expected, value or "")
            if match:
                return False, target, match.group(0)
        return True, targets[0], None
    for target, value in values:
        left = _normalize(value or "", check.normalization) if check.operator == "normalized_equals" else (value or "")
        right = _normalize(expected or "", check.normalization) if check.operator == "normalized_equals" else (expected or "")
        if left == right:
            return True, target, value
    return False, values[0][0], values[0][1]


def _field_value(field: str, text: str, page: str) -> str | None:
    if field == "text":
        return text
    if field == "page_number":
        return page
    if field == "document_type":
        match = re.search(r"(?i)\b(CMM|AMM|SRM|IPC|TSM|WDM|FIM)\b", text)
        return match.group(1).upper() if match else None
    pattern = _ENTITY_PATTERNS.get(field)
    match = pattern.search(text) if pattern else None
    return match.group(1).strip() if match else None


def _normalize(value: str, steps: list[str] | None) -> str:
    for step in steps or []:
        if step == "unicode":
            value = unicodedata.normalize("NFKC", value)
        elif step == "trim":
            value = value.strip()
        elif step == "spaces":
            value = re.sub(r"[ \t]+", " ", value)
        elif step == "line_breaks":
            value = re.sub(r"\s*\r?\n\s*", " ", value)
    return value


def _evidence(
    target: _TextTarget | None,
    observed: str | None,
    expected: str | int | None,
    is_docx: bool,
    pdf_pages: list[ParsedPage] | None,
) -> Evidence:
    target = target or _TextTarget(page="all", text="", raw_page=1)
    if is_docx:
        location = DocxEvidenceLocation(target_id=target.target_id or f"dp{target.raw_page}")
    else:
        bbox = (0.0, 0.0, 0.0, 0.0)
        page = next((item for item in pdf_pages or [] if item.page == target.raw_page), None)
        span = next((item for item in (page.spans if page else []) if observed and observed in item.text), None)
        if span is not None:
            bbox = span.bbox
        location = PdfEvidenceLocation(bbox=bbox)
    return Evidence(
        page=target.page,
        location=location,
        observed_value=observed,
        expected_value=None if expected is None else str(expected),
    )