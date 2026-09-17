"""Evaluation of compiled-rule operators and document-field resolution."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Literal

from app.core.compiled_rules import (
    Check,
    Condition,
    CompiledRule,
    FieldRef,
    RuleResult,
    RuleTarget,
)
from app.parsers.pdf_parser import ParsedPage
from app.core.logging import get_logger

from app.core.compiled_rule_runtime import (
    _ENTITY_PATTERNS,
    _EvalContext,
    _TextTarget,
    evidence,
    scope_targets,
)

_logger = get_logger(__name__)


_PRESSURE_VALUE_PATTERN = r"[+-]?\d+(?:[.,]\d+)?"
_BAR_PRESSURE_RE = re.compile(
    rf"(?P<value>{_PRESSURE_VALUE_PATTERN})\s*bar\b",
    re.IGNORECASE,
)
_BAR_PSI_CONVERSION_RE = re.compile(
    rf"[ \t]*\(\s*(?P<value>{_PRESSURE_VALUE_PATTERN})\s*"
    r"(?:psi|p\s*\.?\s*s\s*\.?\s*i\s*\.?)\s*\)",
    re.IGNORECASE,
)
_PARENTHESIZED_VALUE_RE = re.compile(r"[ \t]*\([^()\r\n]{0,120}\)")
_BAR_TO_PSI = Decimal("14.5037738")
_PRESSURE_DISPLAY_TOLERANCE = Decimal("0.005")
FONT_SIZE_TOLERANCE = 0.1


@dataclass(frozen=True)
class PressureConversionIssue:
    original: str
    proposed: str
    expected: str
    span: tuple[int, int]


def _format_psi(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{rounded:.2f}"


def pressure_conversion_issues(
    text: str,
    policy: str = "bar_to_psi",
) -> list[PressureConversionIssue]:
    """Return bar values missing or carrying an incorrect psi conversion."""
    if policy != "bar_to_psi":
        return []

    issues: list[PressureConversionIssue] = []
    for source_match in _BAR_PRESSURE_RE.finditer(text):
        try:
            bar_value = Decimal(source_match.group("value").replace(",", "."))
        except InvalidOperation:
            continue

        expected_value = bar_value * _BAR_TO_PSI
        expected_conversion = f"({_format_psi(expected_value)} p.s.i.)"
        conversion_match = _BAR_PSI_CONVERSION_RE.match(text, source_match.end())
        original_end = source_match.end()
        valid_conversion = False
        if conversion_match is not None:
            original_end = conversion_match.end()
            try:
                observed_value = Decimal(
                    conversion_match.group("value").replace(",", ".")
                )
            except InvalidOperation:
                observed_value = None
            if observed_value is not None:
                valid_conversion = (
                    abs(observed_value - expected_value)
                    <= _PRESSURE_DISPLAY_TOLERANCE
                )
        else:
            parenthesized = _PARENTHESIZED_VALUE_RE.match(text, source_match.end())
            if parenthesized is not None:
                original_end = parenthesized.end()

        if valid_conversion:
            continue
        source = source_match.group(0)
        issues.append(
            PressureConversionIssue(
                original=text[source_match.start() : original_end],
                proposed=f"{source} {expected_conversion}",
                expected=expected_conversion,
                span=(source_match.start(), original_end),
            )
        )
    return issues


def evaluate_rule(
    rule: CompiledRule,
    targets: list[_TextTarget],
    is_docx: bool,
    pdf_pages: list[ParsedPage] | None,
    ctx: _EvalContext,
) -> RuleResult:
    last_target = targets[0]
    last_observed: str | None = None
    last_expected: str | None = None
    first_failure: tuple[
        Literal["PASS", "FAIL", "INCONCLUSIVE"],
        _TextTarget,
        str | None,
        str | None,
    ] | None = None
    for check_index, check in enumerate(rule.checks):
        status, target, observed, expected_repr = evaluate_check(
            check,
            targets,
            ctx,
            rule.id,
        )
        last_target, last_observed, last_expected = target, observed, expected_repr
        _logger.info(
            "compiled_check_evaluated",
            rule_id=rule.id,
            check_index=check_index,
            check=check.model_dump(mode="json"),
            status=status,
            page=target.page,
            observed=observed,
            expected=expected_repr,
        )
        if status != "PASS" and first_failure is None:
            first_failure = (status, target, observed, expected_repr)
    if first_failure is not None:
        status, target, observed, expected_repr = first_failure
        result_evidence = evidence(target, observed, expected_repr, is_docx, pdf_pages)
        return RuleResult(rule_id=rule.id, status=status, evidence=result_evidence)
    return RuleResult(
        rule_id=rule.id,
        status="PASS",
        evidence=evidence(last_target, last_observed, last_expected, is_docx, pdf_pages),
    )


def evaluate_check(
    check: Check,
    targets: list[_TextTarget],
    ctx: _EvalContext,
    rule_id: str,
) -> tuple[Literal["PASS", "FAIL", "INCONCLUSIVE"], _TextTarget, str | None, str | None]:
    values = [(target, field_value(check.field, target.text, target.page)) for target in targets]
    expected = None if check.expected is None or isinstance(check.expected, list) else str(check.expected)
    if check.operator == "exists":
        match = next(((target, value) for target, value in values if value and (expected is None or expected in value)), None)
        target, observed = match or (targets[0], None)
        return ("PASS" if match is not None else "FAIL"), target, observed, expected
    if check.operator == "not_exists":
        match = next(((target, value) for target, value in values if value and (expected is None or expected in value)), None)
        target, observed = (targets[0], None) if match is None else match
        return ("PASS" if match is None else "FAIL"), target, observed, expected
    if check.operator in {"regex", "regex_exists"}:
        return evaluate_regex(check, values, rule_id, ctx)
    if check.operator == "font_size_equals":
        return evaluate_font_size(check, targets, ctx)
    if check.operator == "pressure_conversion":
        policy = str(check.expected)
        for target, value in values:
            issues = pressure_conversion_issues(value or "", policy)
            if issues:
                issue = issues[0]
                return "FAIL", target, issue.original, issue.expected
        return "PASS", values[0][0], None, policy
    if check.operator == "contains_any":
        terms = [str(term) for term in (check.expected or [])]
        joined = ", ".join(terms)
        for target, value in values:
            if not value:
                continue
            hit = next((term for term in terms if term in value), None)
            if hit:
                return "PASS", target, hit, joined
        return "FAIL", targets[0], None, joined
    if check.operator == "contains_all":
        terms = [str(term) for term in (check.expected or [])]
        joined = ", ".join(terms)
        last_hit_target = targets[0]
        for term in terms:
            hit = next(((target, value) for target, value in values if value and term in value), None)
            if hit is None:
                return "FAIL", last_hit_target, None, term
            last_hit_target = hit[0]
        return "PASS", last_hit_target, joined, joined
    if check.operator == "contains_none":
        terms = [str(term) for term in (check.expected or [])]
        for target, value in values:
            if not value:
                continue
            hit = next((term for term in terms if term in value), None)
            if hit:
                return "FAIL", target, hit, ", ".join(terms)
        return "PASS", targets[0], None, ", ".join(terms)
    if check.operator == "equals_field":
        assert check.compare_to is not None
        right_target, right_value = resolve_field_ref(check.compare_to, ctx)
        if right_value is None:
            left = next(
                ((target, normalize(value, check.normalization)) for target, value in values if value),
                None,
            )
            fallback = left[0] if left else (right_target or targets[0])
            observed = left[1] if left else None
            return "INCONCLUSIVE", fallback, observed, right_value

        first_missing: tuple[_TextTarget, None] | None = None
        first_mismatch: tuple[_TextTarget, str] | None = None
        last_match: tuple[_TextTarget, str] | None = None
        for target, value in values:
            if not value:
                if first_missing is None:
                    first_missing = (target, None)
                continue
            observed = normalize(value, check.normalization)
            if observed != right_value and first_mismatch is None:
                first_mismatch = (target, observed)
            elif observed == right_value:
                last_match = (target, observed)

        if first_mismatch is not None:
            target, observed = first_mismatch
            return "FAIL", target, observed, right_value
        if first_missing is not None:
            target, _observed = first_missing
            return "INCONCLUSIVE", target, None, right_value
        if last_match is not None:
            target, observed = last_match
            return "PASS", target, observed, right_value
        return "INCONCLUSIVE", targets[0], None, right_value
    if check.operator == "normalized_equals":
        expected_value = normalize(expected or "", check.normalization)
        first_missing: tuple[_TextTarget, None] | None = None
        first_mismatch: tuple[_TextTarget, str] | None = None
        last_match: tuple[_TextTarget, str] | None = None
        for target, value in values:
            if not value:
                if first_missing is None:
                    first_missing = (target, None)
                continue
            observed = normalize(value, check.normalization)
            if observed != expected_value and first_mismatch is None:
                first_mismatch = (target, observed)
            elif observed == expected_value:
                last_match = (target, observed)

        if first_mismatch is not None:
            target, observed = first_mismatch
            return "FAIL", target, observed, expected_value
        if first_missing is not None:
            target = first_missing[0]
            return "INCONCLUSIVE", target, None, expected_value
        if last_match is not None:
            target, observed = last_match
            return "PASS", target, observed, expected_value
        return "INCONCLUSIVE", targets[0], None, expected_value
    for target, value in values:
        left = value or ""
        right = expected or ""
        if left == right:
            return "PASS", target, value, expected
    return "FAIL", values[0][0], values[0][1], expected


def field_value(field: str, text: str, page: str) -> str | None:
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


def matching_font_spans(
    check: Check,
    target: _TextTarget,
) -> list[tuple[int, int, str, tuple[float, float, float, float], float, str]]:
    """Return spans matching the entity and any logo-specific identity rules."""
    matches: list[tuple[int, int, str, tuple[float, float, float, float], float, str]] = []
    for start, end, bbox, size, font in target.span_ranges:
        original = target.text[start:end]
        if field_value(check.field, original, target.page) is None:
            continue
        if check.field == "thales_logo_t":
            if start != 0 or original.strip() != "T" or "thales" not in font.casefold():
                continue
        matches.append((start, end, original, bbox, size, font))
    return matches


def evaluate_font_size(
    check: Check,
    targets: list[_TextTarget],
    ctx: _EvalContext,
) -> tuple[Literal["PASS", "FAIL", "INCONCLUSIVE"], _TextTarget, str | None, str | None]:
    """Compare the font size of spans matching the requested entity field."""
    if ctx.is_docx or not ctx.pdf_pages:
        return "INCONCLUSIVE", targets[0], None, f"{check.expected} pt"

    expected_size = float(check.expected)
    first_missing: _TextTarget | None = None
    first_mismatch: tuple[_TextTarget, float] | None = None
    last_match: tuple[_TextTarget, float] | None = None

    for target in targets:
        matching_sizes = [
            (original, size)
            for _start, _end, original, _bbox, size, _font in matching_font_spans(check, target)
        ]
        if not matching_sizes:
            if first_missing is None:
                first_missing = target
            continue
        for _observed_text, observed_size in matching_sizes:
            if abs(observed_size - expected_size) > FONT_SIZE_TOLERANCE:
                if first_mismatch is None:
                    first_mismatch = (target, observed_size)
            else:
                last_match = (target, observed_size)

    expected_display = f"{expected_size:g} pt"
    if first_mismatch is not None:
        target, observed_size = first_mismatch
        return "FAIL", target, f"{observed_size:.0f} pt", expected_display
    if first_missing is not None:
        status: Literal["FAIL", "INCONCLUSIVE"] = (
            "FAIL" if check.field == "thales_logo_t" else "INCONCLUSIVE"
        )
        return status, first_missing, None, expected_display
    if last_match is not None:
        target, observed_size = last_match
        return "PASS", target, f"{observed_size:.0f} pt", expected_display
    return "INCONCLUSIVE", targets[0], None, expected_display


def extract_year(value: str) -> str:
    """Extract the last year from a copyright or revision-date value."""
    four_digit = re.findall(r"\d{4}", value)
    if four_digit:
        return four_digit[-1]
    two_digit = re.findall(r"(?<!\d)\d{2}(?!\d)", value)
    if two_digit:
        return f"20{two_digit[-1]}"
    return value


def normalize(value: str, steps: list[str] | None) -> str:
    for step in steps or []:
        if step == "unicode":
            value = unicodedata.normalize("NFKC", value)
        elif step == "trim":
            value = value.strip()
        elif step == "spaces":
            value = re.sub(r"[ \t]+", " ", value)
        elif step == "line_breaks":
            value = re.sub(r"\s*\r?\n\s*", " ", value)
        elif step == "extract_year":
            value = extract_year(value)
    return value


def condition_met(condition: Condition, ctx: _EvalContext) -> bool:
    value = resolve_meta_value(condition.field, ctx.document)
    present = bool(value and value.strip())
    return present if condition.state == "present" else not present


def resolve_meta_value(field: str, document: Any | None) -> str | None:
    value = getattr(document, field, None) if document is not None else None
    if value and str(value).strip():
        return str(value).strip()
    return None


def resolve_field_ref(ref: FieldRef, ctx: _EvalContext) -> tuple[_TextTarget | None, str | None]:
    if ref.source == "document_meta":
        raw = resolve_meta_value(ref.field, ctx.document)
        return None, (normalize(raw, ref.normalization) if raw is not None else None)
    scoped = scope_targets(
        RuleTarget(page=ref.page, region=ref.region),
        ctx.all_targets,
        is_docx=ctx.is_docx,
        blocks=ctx.blocks,
        pdf_pages=ctx.pdf_pages,
    )
    if not scoped:
        return None, None
    for target in scoped:
        raw = field_value(ref.field, target.text, target.page)
        if raw:
            return target, normalize(raw, ref.normalization)
    return scoped[0], None


def evaluate_regex(
    check: Check,
    values: list[tuple[_TextTarget, str | None]],
    rule_id: str,
    ctx: _EvalContext,
) -> tuple[Literal["PASS", "FAIL", "INCONCLUSIVE"], _TextTarget, str | None, str | None]:
    expected = None if check.expected is None else str(check.expected)
    if expected is None:
        return "FAIL", values[0][0], None, expected
    resolved_pattern, context_fields, missing_context = resolve_regex_pattern(expected, ctx)
    if missing_context:
        return "INCONCLUSIVE", values[0][0], None, expected
    try:
        pattern = re.compile(resolved_pattern)
    except re.error:
        return "INCONCLUSIVE", values[0][0], None, expected

    first_match: tuple[_TextTarget, re.Match[str]] | None = None
    for target, value in values:
        text = value or ""
        matches = list(pattern.finditer(text))
        _logger.info(
            "compiled_regex_evaluated",
            rule_id=rule_id,
            page=target.page,
            pattern=resolved_pattern,
            match_count=len(matches),
            document_metadata={
                field: str(raw).strip()
                for field in (
                    "meta_revision_date",
                    "meta_cmm_number",
                    "meta_first_issue_date",
                    "meta_revision_number",
                    "meta_pnr_number",
                    "document_language",
                )
                if (raw := getattr(ctx.document, field, None)) is not None and str(raw).strip()
            },
        )
        if matches and first_match is None:
            first_match = (target, matches[0])

    if check.operator == "regex":
        if first_match is not None:
            target, match = first_match
            return "FAIL", target, match.group(0), expected
        return "PASS", values[0][0], None, expected
    if check.require_all:
        missing_target = next(
            (target for target, _value in values if not pattern.search(_value or "")),
            None,
        )
        if missing_target is None:
            target, match = first_match or (values[0][0], pattern.search(values[0][1] or ""))
            return "PASS", target, match.group(0) if match is not None else None, expected
        return "FAIL", missing_target, None, expected
    if first_match is not None:
        target, match = first_match
        return "PASS", target, match.group(0), expected
    return "FAIL", values[0][0], None, expected


def resolve_regex_pattern(
    pattern: str,
    ctx: _EvalContext,
) -> tuple[str, list[str], list[str]]:
    from app.core.compiled_rule_runtime import _CONTEXT_TOKEN_RE, document_metadata

    metadata = document_metadata(ctx.document)
    context_fields: list[str] = []
    missing_context: list[str] = []

    def replace_token(match: re.Match[str]) -> str:
        field = match.group(1)
        if field not in context_fields:
            context_fields.append(field)
        value = metadata.get(field)
        if value is None:
            missing_context.append(field)
            return match.group(0)
        return re.escape(value)

    resolved = _CONTEXT_TOKEN_RE.sub(replace_token, pattern)
    return resolved, context_fields, sorted(set(missing_context))


def resolve_replacement_template(template: str | None, document: Any | None) -> str | None:
    from app.core.compiled_rule_runtime import _CONTEXT_TOKEN_RE, document_metadata

    if template is None:
        return None
    metadata = document_metadata(document)
    missing_context = False

    def replace_token(match: re.Match[str]) -> str:
        nonlocal missing_context
        value = metadata.get(match.group(1))
        if value is None:
            missing_context = True
            return match.group(0)
        return value.replace("\\", "\\\\")

    resolved = _CONTEXT_TOKEN_RE.sub(replace_token, template)
    return None if missing_context else resolved
