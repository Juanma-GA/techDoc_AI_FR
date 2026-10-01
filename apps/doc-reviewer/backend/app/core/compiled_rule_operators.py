"""Evaluation of compiled-rule operators and document-field resolution."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, Literal

from app.checks.client_bundle import (
    ClientOperationContext,
    OperationResult,
)
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
from app.core.regex_safety import (
    USER_REGEX_TIMEOUT_SECONDS,
    UserRegexPatternError,
    compile_user_regex,
)

from app.core.compiled_rule_runtime import (
    _ENTITY_PATTERNS,
    _EvalContext,
    _SpanRange,
    _TextTarget,
    evidence,
    scope_targets,
)

_logger = get_logger(__name__)


@dataclass(frozen=True)
class UnitConversionPolicy:
    source_pattern: re.Pattern[str]
    target_pattern: re.Pattern[str]
    factors: Mapping[str, Decimal]
    target_unit: str
    source_modifier_pattern: re.Pattern[str] | None = None
    significant_digits: int | None = None


_PRESSURE_VALUE_PATTERN = r"[+-]?\d+(?:[.,]\d+)?"
_PERCENT_UNCERTAINTY_PATTERN = re.compile(
    r"[ \t]*(?P<modifier>(?:\+/-|\+-|\+|\u00b1)[ \t]*"
    rf"[+-]?{_PRESSURE_VALUE_PATTERN}[ \t]*%)"
)
_BAR_PRESSURE_RE = re.compile(
    rf"(?P<value>{_PRESSURE_VALUE_PATTERN})\s*(?P<unit>bar)\b",
    re.IGNORECASE,
)
_BAR_PSI_CONVERSION_RE = re.compile(
    rf"[ \t]*\(\s*(?P<value>{_PRESSURE_VALUE_PATTERN})\s*"
    r"(?:psi|p\s*\.?\s*s\s*\.?\s*i\s*\.?)"
    r"(?P<modifier>[ \t]*(?:\+/-|\+-|\+|\u00b1)[ \t]*"
    rf"[+-]?{_PRESSURE_VALUE_PATTERN}[ \t]*%)?\s*\)",
    re.IGNORECASE,
)
_PARENTHESIZED_VALUE_RE = re.compile(r"[ \t]*\([^()\r\n]{0,120}\)")
_BAR_TO_PSI = Decimal("14.5037738")
_KG_TO_LB = Decimal(1) / Decimal("0.45359237")
_NM_TO_LBF_IN = Decimal("8.850745767378715")
_UNIT_CONVERSION_POLICIES = {
    "bar_to_psi": UnitConversionPolicy(
        source_pattern=_BAR_PRESSURE_RE,
        target_pattern=_BAR_PSI_CONVERSION_RE,
        factors={"bar": _BAR_TO_PSI},
        target_unit="p.s.i.",
        source_modifier_pattern=_PERCENT_UNCERTAINTY_PATTERN,
        significant_digits=4,
    ),
    "pascal_to_inhg": UnitConversionPolicy(
        source_pattern=re.compile(
            rf"(?<![\w.])(?P<value>{_PRESSURE_VALUE_PATTERN})\s*"
            r"(?P<unit>GPa|MPa|kPa|hPa|Pa)\b"
        ),
        target_pattern=re.compile(
            rf"[ \t]*\(\s*(?P<value>{_PRESSURE_VALUE_PATTERN})\s*"
            r"in\s*\.?\s*Hg"
            r"(?P<modifier>[ \t]*(?:\+/-|\+-|\+|\u00b1)[ \t]*"
            rf"[+-]?{_PRESSURE_VALUE_PATTERN}[ \t]*%)?\s*\)",
            re.IGNORECASE,
        ),
        factors={
            "pa": Decimal(1) / Decimal("3386.389"),
            "hpa": Decimal(100) / Decimal("3386.389"),
            "kpa": Decimal(1000) / Decimal("3386.389"),
            "mpa": Decimal("1000000") / Decimal("3386.389"),
            "gpa": Decimal("1000000000") / Decimal("3386.389"),
        },
        target_unit="inHg",
        source_modifier_pattern=_PERCENT_UNCERTAINTY_PATTERN,
    ),
    "metric_length_to_inch": UnitConversionPolicy(
        source_pattern=re.compile(
            rf"(?<![\w.])(?P<value>{_PRESSURE_VALUE_PATTERN})\s*"
            r"(?P<unit>km|cm|mm|m)\b",
            re.IGNORECASE,
        ),
        target_pattern=re.compile(
            rf"[ \t]*\(\s*(?P<value>{_PRESSURE_VALUE_PATTERN})\s*"
            r"(?:inch(?:es)?|in\.?)"
            r"(?P<modifier>[ \t]*(?:\+/-|\+-|\+|\u00b1)[ \t]*"
            rf"[+-]?{_PRESSURE_VALUE_PATTERN}[ \t]*%)?\s*\)",
            re.IGNORECASE,
        ),
        factors={
            "mm": Decimal(1) / Decimal("25.4"),
            "cm": Decimal(10) / Decimal("25.4"),
            "m": Decimal(1000) / Decimal("25.4"),
            "km": Decimal("1000000") / Decimal("25.4"),
        },
        target_unit="in.",
        source_modifier_pattern=_PERCENT_UNCERTAINTY_PATTERN,
    ),
    "metric_mass_to_lb": UnitConversionPolicy(
        source_pattern=re.compile(
            rf"(?<![\w.])(?P<value>{_PRESSURE_VALUE_PATTERN})\s*"
            r"(?P<unit>tonnes?|kg|mg|g|t)\b",
            re.IGNORECASE,
        ),
        target_pattern=re.compile(
            rf"[ \t]*\(\s*(?P<value>{_PRESSURE_VALUE_PATTERN})\s*lb\b"
            r"(?P<modifier>[ \t]*(?:\+/-|\+-|\+|\u00b1)[ \t]*"
            rf"[+-]?{_PRESSURE_VALUE_PATTERN}[ \t]*%)?\s*\)",
            re.IGNORECASE,
        ),
        factors={
            "mg": _KG_TO_LB / Decimal("1000000"),
            "g": _KG_TO_LB / Decimal("1000"),
            "kg": _KG_TO_LB,
            "t": _KG_TO_LB * Decimal("1000"),
            "tonne": _KG_TO_LB * Decimal("1000"),
            "tonnes": _KG_TO_LB * Decimal("1000"),
        },
        target_unit="lb",
        source_modifier_pattern=_PERCENT_UNCERTAINTY_PATTERN,
        significant_digits=3,
    ),
    "metric_torque_to_lbf_in": UnitConversionPolicy(
        source_pattern=re.compile(
            rf"(?<![\w.])(?P<value>{_PRESSURE_VALUE_PATTERN})\s*"
            r"(?P<force_unit>kN|daN|N)\s*(?:[.·*]\s*)?"
            r"(?P<length_unit>mm|cm|m)\b"
        ),
        target_pattern=re.compile(
            rf"[ \t]*\(\s*(?P<value>{_PRESSURE_VALUE_PATTERN})\s*"
            r"lbf\s*(?:[.·*]\s*|\s+)in"
            r"(?P<modifier>[ \t]*(?:\+/-|\+-|\+|\u00b1)[ \t]*"
            rf"[+-]?{_PRESSURE_VALUE_PATTERN}[ \t]*%)?\s*\)",
            re.IGNORECASE,
        ),
        factors={
            f"{force_unit}:{length_unit}": Decimal(force_factor)
            * Decimal(length_factor)
            * _NM_TO_LBF_IN
            for force_unit, force_factor in (("N", 1), ("daN", 10), ("kN", 1000))
            for length_unit, length_factor in (("mm", "0.001"), ("cm", "0.01"), ("m", 1))
        },
        target_unit="lbf.in",
        source_modifier_pattern=_PERCENT_UNCERTAINTY_PATTERN,
    ),
}
FONT_SIZE_TOLERANCE = 0.1
_ENUMERATION_START_RE = re.compile(
    r"^\s*(?P<marker>(?:[-*]|\([A-Za-z0-9]+\)|[A-Z]\.\s*|\d+[.)]\s+))"
)
# Parenthesized procedure steps are intentionally ignored for now; this policy
# can be narrowed later without changing the rest of the punctuation scanner.
_IGNORED_PARENTHESIZED_STEP_RE = re.compile(r"^\s*\([A-Za-z0-9]+\)(?:\s|$)")
_DATE_ONLY_RE = re.compile(
    r"(?i)^\s*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+"
    r"\d{1,2}(?:\s*/\s*\d{2,4})?\s*$"
)
_PAGE_LABEL_RE = re.compile(
    r"(?i)^\s*(?:TP|ROR|LEP|TC|INTRO|HIGHLIGHTS|PAGE)\s+"
    r"(?:PAGE\s+)?\d+\s*$"
)
_HEADING_RE = re.compile(r"^\s*(?:\d+\.\s+|[A-Z]\.\s+)[A-Z].*$")
_STRUCTURAL_PAGE_RE = re.compile(
    r"(?im)^\s*(?:HIGHLIGHTS|LIST OF EFFECTIVE PAGES|"
    r"RECORD OF REVISIONS|TABLE OF CONTENTS)\s*$"
)
_STRUCTURAL_PAGE_TYPES = frozenset(
    {"TP1", "TP2", "HIGHLIGHTS", "HIGHLIGHTS_PAGE_1"}
)
_IMPORTANT_NOTICE_START_RE = re.compile(r"(?im)^\s*IMPORTANT NOTICE\s*$")
_IMPORTANT_NOTICE_END_RE = re.compile(
    r"(?im)^\s*https://www\.thalesgroup\.com/customer-online\s*$"
)


@dataclass(frozen=True)
class PressureConversionIssue:
    original: str
    proposed: str
    expected: str
    span: tuple[int, int]


@dataclass(frozen=True)
class SentencePunctuationIssue:
    original: str
    proposed: str
    expected: str
    span: tuple[int, int]


@dataclass(frozen=True)
class _PunctuationBlock:
    text: str
    last_line: str
    start: int
    end: int
    last_start: int
    last_end: int


def pressure_conversion_issues(
    text: str,
    policy: str = "bar_to_psi",
) -> list[PressureConversionIssue]:
    """Return bar values missing or carrying an incorrect psi conversion."""
    return unit_conversion_issues(text, policy)


def _uncertainty_key(modifier: str | None) -> tuple[str, Decimal] | None:
    if modifier is None:
        return None
    match = re.fullmatch(
        rf"(?:\+/-|\+-|\+|\u00b1)\s*"
        rf"(?P<value>[+-]?{_PRESSURE_VALUE_PATTERN})\s*%",
        modifier.strip(),
    )
    if match is None:
        return None
    try:
        value = Decimal(match.group("value").replace(",", "."))
    except InvalidOperation:
        return None
    return "plus_minus_percent", value


def _uncertainty_matches(source: str | None, converted: str | None) -> bool:
    return _uncertainty_key(source) == _uncertainty_key(converted)


def unit_conversion_issues(
    text: str,
    policy: str,
) -> list[PressureConversionIssue]:
    """Return SI values missing or carrying an incorrect paired conversion."""
    conversion_policy = _UNIT_CONVERSION_POLICIES.get(policy)
    if conversion_policy is None:
        return []

    issues: list[PressureConversionIssue] = []
    ignored_until = 0
    for source_match in conversion_policy.source_pattern.finditer(text):
        if source_match.start() < ignored_until:
            continue
        try:
            source_value = Decimal(source_match.group("value").replace(",", "."))
        except InvalidOperation:
            continue

        if "force_unit" in source_match.groupdict():
            unit_key = (
                f"{source_match.group('force_unit')}:"
                f"{source_match.group('length_unit')}"
            )
        else:
            unit_key = source_match.group("unit").casefold()
        factor = conversion_policy.factors.get(unit_key)
        if factor is None:
            continue

        source_modifier_match = (
            conversion_policy.source_modifier_pattern.match(text, source_match.end())
            if conversion_policy.source_modifier_pattern is not None
            else None
        )
        conversion_start = (
            source_modifier_match.end()
            if source_modifier_match is not None
            else source_match.end()
        )
        source_modifier = (
            source_modifier_match.group("modifier")
            if source_modifier_match is not None
            else None
        )

        expected_value = source_value * factor
        if conversion_policy.significant_digits is not None and expected_value != 0:
            precision = (
                conversion_policy.significant_digits - 1 - expected_value.adjusted()
            )
        elif conversion_policy.significant_digits is not None:
            precision = conversion_policy.significant_digits - 1
        else:
            absolute_value = abs(expected_value)
            precision = (
                2
                if absolute_value >= Decimal("0.01") or absolute_value == 0
                else 4
                if absolute_value >= Decimal("0.0001")
                else 8
            )
        display_quantum = Decimal(1).scaleb(-precision)
        formatted_value = expected_value.quantize(
            display_quantum,
            rounding=ROUND_HALF_UP,
        )
        rendered_precision = max(precision, 0)
        expected_conversion = (
            f"({formatted_value:.{rendered_precision}f} {conversion_policy.target_unit}"
        )
        if source_modifier is not None:
            expected_conversion += f" {source_modifier}"
        expected_conversion += ")"
        conversion_match = conversion_policy.target_pattern.match(
            text,
            conversion_start,
        )
        original_end = conversion_start
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
                    abs(observed_value - expected_value) <= display_quantum / 2
                )
                observed_modifier = conversion_match.groupdict().get("modifier")
                valid_conversion = valid_conversion and _uncertainty_matches(
                    source_modifier,
                    observed_modifier,
                )
        else:
            parenthesized = _PARENTHESIZED_VALUE_RE.match(text, conversion_start)
            if parenthesized is not None:
                original_end = parenthesized.end()
                ignored_until = original_end

        if valid_conversion:
            continue
        source = text[source_match.start() : conversion_start]
        issues.append(
            PressureConversionIssue(
                original=text[source_match.start() : original_end],
            proposed=f"{source} {expected_conversion}",
                expected=expected_conversion,
                span=(source_match.start(), original_end),
            )
        )
    return issues


def _punctuation_blocks(text: str) -> list[_PunctuationBlock]:
    blocks: list[_PunctuationBlock] = []
    current: list[tuple[str, int, int]] = []
    offset = 0

    def flush() -> None:
        if not current:
            return
        blocks.append(
            _PunctuationBlock(
                text=" ".join(line for line, _start, _end in current),
                last_line=current[-1][0],
                start=current[0][1],
                end=current[-1][2],
                last_start=current[-1][1],
                last_end=current[-1][2],
            )
        )
        current.clear()

    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        line_start = offset
        offset += len(raw_line)
        if not line.strip():
            flush()
            continue
        if current and (
            line.strip() in {"-", "*"}
            or _ENUMERATION_START_RE.match(line.strip()) is not None
        ):
            flush()
        leading = len(line) - len(line.lstrip())
        trailing = len(line.rstrip())
        current.append(
            (line.strip(), line_start + leading, line_start + trailing)
        )
    flush()
    return blocks


def _block_span_ranges(
    block: _PunctuationBlock,
    span_ranges: tuple[_SpanRange, ...],
) -> list[_SpanRange]:
    return [
        item
        for item in span_ranges
        if item[1] > block.start and item[0] < block.end
    ]


def _block_is_outside_body(
    block: _PunctuationBlock,
    span_ranges: tuple[_SpanRange, ...],
) -> bool:
    relevant = _block_span_ranges(block, span_ranges)
    if not relevant:
        return False
    min_y = min(item[2][1] for item in span_ranges)
    max_y = max(item[2][3] for item in span_ranges)
    height = max_y - min_y
    if height <= 0:
        return False
    centers = [(item[2][1] + item[2][3]) / 2 for item in relevant]
    return max(centers) <= min_y + height * 0.25 or min(centers) >= max_y - height * 0.25


def _block_is_table_like(
    block: _PunctuationBlock,
    span_ranges: tuple[_SpanRange, ...],
) -> bool:
    relevant = _block_span_ranges(block, span_ranges)
    if not relevant:
        return False
    rows: list[tuple[float, list[_SpanRange]]] = []
    for item in sorted(span_ranges, key=lambda item: item[2][1]):
        center = (item[2][1] + item[2][3]) / 2
        if rows and abs(center - rows[-1][0]) <= 3.0:
            rows[-1][1].append(item)
        else:
            rows.append((center, [item]))
    table_rows = [
        row
        for row in rows
        if len(row[1]) >= 3
        and max(item[2][0] for item in row[1])
        - min(item[2][0] for item in row[1])
        > 40.0
    ]
    if len(table_rows) < 3:
        return False
    table_top = min(item[2][1] for _center, row in table_rows for item in row) - 70.0
    table_bottom = max(item[2][3] for _center, row in table_rows for item in row) + 5.0
    return any(
        table_top
        <= (item[2][1] + item[2][3]) / 2
        <= table_bottom
        for item in relevant
    )


def _is_non_sentence_block(text: str) -> bool:
    compact = " ".join(text.split())
    if not compact:
        return True
    if compact in {"T", "OVERHAUL MANUAL"}:
        return True
    if not re.search(r"[a-z]", compact):
        return True
    if (
        "THALES AVS FRANCE SAS" in compact
        or compact.startswith("https://")
        or "@" in compact
    ):
        return True
    if _DATE_ONLY_RE.fullmatch(compact) or _PAGE_LABEL_RE.fullmatch(compact):
        return True
    if re.fullmatch(
        r"\d{2}-\d{2}-\d{2}|\d+-\d+-[A-Z]+|1-\d{3}-[A-Z]{2}",
        compact,
    ):
        return True
    if re.match(r"(?i)^\s*(?:table|figure)\s+\d+\b", compact):
        return True
    if _HEADING_RE.fullmatch(compact):
        return True
    return False


def _enumeration_family(text: str) -> str | None:
    match = _ENUMERATION_START_RE.match(text)
    if match is None:
        return None
    marker = match.group("marker").strip()
    if marker in {"-", "*"}:
        return "bullet"
    if marker.startswith("("):
        return None
    if marker[0].isdigit():
        return "number"
    return "letter"


def _replace_terminal_punctuation(value: str, expected: str) -> str:
    stripped = value.rstrip()
    closing_quotes = ""
    while stripped and stripped[-1] in "\"'»”":
        closing_quotes = stripped[-1] + closing_quotes
        stripped = stripped[:-1].rstrip()
    if stripped and stripped[-1] in ".,;:!?":
        stripped = stripped[:-1]
    return f"{stripped}{expected}{closing_quotes}"


def sentence_punctuation_issues(
    text: str,
    span_ranges: tuple[_SpanRange, ...] = (),
    *,
    skip_page: bool = False,
    policy: str = "period_and_enumeration",
) -> list[SentencePunctuationIssue]:
    if skip_page or _STRUCTURAL_PAGE_RE.search(text):
        return []
    blocks = _punctuation_blocks(text)
    candidates = [
        block
        for block in blocks
        if not _block_is_outside_body(block, span_ranges)
        and not _block_is_table_like(block, span_ranges)
        and not _IGNORED_PARENTHESIZED_STEP_RE.match(block.text)
        and not _is_non_sentence_block(block.text)
    ]
    classified = [(block, _enumeration_family(block.text)) for block in candidates]
    issues: list[SentencePunctuationIssue] = []
    for index, (block, family) in enumerate(classified):
        next_family = classified[index + 1][1] if index + 1 < len(classified) else None
        if family is None:
            expected = "."
            if block.text.rstrip().endswith(":"):
                continue
        else:
            group_end = index
            while (
                group_end + 1 < len(classified)
                and classified[group_end + 1][1] == family
            ):
                group_end += 1
            expected = "," if group_end > index else "."
            if (
                block.text.rstrip().endswith(":")
                and next_family is not None
                and next_family != family
            ):
                continue
        observed = block.last_line.rstrip()
        terminal = observed.rstrip()
        while terminal and terminal[-1] in "\"'»”":
            terminal = terminal[:-1].rstrip()
        if terminal.endswith(expected):
            continue
        terminal_punctuation = terminal[-1] if terminal else ""
        enumeration_swap = (
            family is not None
            and terminal_punctuation in {".", ","}
            and terminal_punctuation != expected
        )
        if policy == "missing_required_punctuation" and enumeration_swap:
            continue
        if policy == "enumeration_punctuation_swap" and not enumeration_swap:
            continue
        issues.append(
            SentencePunctuationIssue(
                original=observed,
                proposed=_replace_terminal_punctuation(observed, expected),
                expected=expected,
                span=(block.last_start, block.last_end),
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
            status=status,
            page=target.page,
        )
        if status != "PASS" and first_failure is None:
            first_failure = (status, target, observed, expected_repr)
    inconclusive_pages = ctx.inconclusive_pages.pop(rule.id, [])
    if first_failure is not None:
        status, target, observed, expected_repr = first_failure
        result_evidence = evidence(target, observed, expected_repr, is_docx, pdf_pages)
        return RuleResult(
            rule_id=rule.id,
            status=status,
            evidence=result_evidence,
            inconclusive_pages=[str(page) for page in inconclusive_pages]
            if status == "INCONCLUSIVE"
            else [],
        )
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
    values = [
        (
            target,
            field_value(
                check.field,
                target.text,
                target.page,
                ctx.client_entities,
            ),
        )
        for target in targets
    ]
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
    if check.operator == "unit_conversion":
        policy = str(check.expected)
        for target, value in values:
            issues = unit_conversion_issues(value or "", policy)
            if issues:
                issue = issues[0]
                return "FAIL", target, issue.original, issue.expected
        return "PASS", values[0][0], None, policy
    if check.operator == "sentence_punctuation":
        for target, value in values:
            issues = sentence_punctuation_issues(
                value or "",
                target.span_ranges,
                skip_page=target.page_type in _STRUCTURAL_PAGE_TYPES,
                policy=str(check.expected),
            )
            if issues:
                issue = issues[0]
                return "FAIL", target, issue.original, issue.proposed
        return "PASS", values[0][0], None, str(check.expected)
    if check.operator in {
        "client_operation",
        "revision_consistency",
        "shop_verification",
        "highlights_holder",
        "highlights_document_type",
    }:
        return evaluate_client_operation(check, targets, ctx, rule_id)
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

        right_values = right_value if isinstance(right_value, list) else [right_value]
        expected_display = (
            json.dumps(right_values, ensure_ascii=False)
            if isinstance(right_value, list)
            else right_value
        )

        first_missing: tuple[_TextTarget, None] | None = None
        first_mismatch: tuple[_TextTarget, str] | None = None
        last_match: tuple[_TextTarget, str] | None = None
        for target, value in values:
            if not value:
                if first_missing is None:
                    first_missing = (target, None)
                continue
            observed = normalize(value, check.normalization)
            if observed not in right_values and first_mismatch is None:
                first_mismatch = (target, observed)
            elif observed in right_values:
                last_match = (target, observed)

        if first_mismatch is not None:
            target, observed = first_mismatch
            return "FAIL", target, observed, expected_display
        if first_missing is not None:
            target, _observed = first_missing
            return "INCONCLUSIVE", target, None, expected_display
        if last_match is not None:
            target, observed = last_match
            return "PASS", target, observed, expected_display
        return "INCONCLUSIVE", targets[0], None, expected_display
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
            status: Literal["FAIL", "INCONCLUSIVE"] = (
                "FAIL" if check.field == "important_notice" else "INCONCLUSIVE"
            )
            return status, target, None, expected_value
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


def field_value(
    field: str,
    text: str,
    page: str,
    client_entities: Mapping[str, str] | None = None,
) -> str | None:
    if field == "text":
        return text
    if field == "page_number":
        return page
    if field == "document_type":
        match = re.search(r"(?i)\b(CMM|AMM|SRM|IPC|TSM|WDM|FIM)\b", text)
        return match.group(1).upper() if match else None
    if field == "important_notice":
        start = _IMPORTANT_NOTICE_START_RE.search(text)
        if start is None:
            return None
        end = _IMPORTANT_NOTICE_END_RE.search(text, start.end())
        if end is None:
            return None
        return text[start.start() : end.end()].strip()
    pattern_text = (client_entities or {}).get(field)
    if pattern_text is not None:
        pattern = compile_user_regex(pattern_text)
        match = pattern.search(text, timeout=USER_REGEX_TIMEOUT_SECONDS)
    else:
        pattern = _ENTITY_PATTERNS.get(field)
        match = pattern.search(text) if pattern else None
    return match.group(1).strip() if match else None


def matching_font_spans(
    check: Check,
    target: _TextTarget,
    client_entities: Mapping[str, str] | None = None,
) -> list[tuple[int, int, str, tuple[float, float, float, float], float, str]]:
    """Return spans matching the entity and any logo-specific identity rules."""
    matches: list[tuple[int, int, str, tuple[float, float, float, float], float, str]] = []
    for start, end, bbox, size, font in target.span_ranges:
        original = target.text[start:end]
        if field_value(check.field, original, target.page, client_entities) is None:
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
            for _start, _end, original, _bbox, size, _font in matching_font_spans(
                check,
                target,
                ctx.client_entities,
            )
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


def evaluate_client_operation(
    check: Check,
    targets: list[_TextTarget],
    ctx: _EvalContext,
    rule_id: str,
) -> tuple[Literal["PASS", "FAIL", "INCONCLUSIVE"], _TextTarget, str | None, str | None]:
    operation_name = check.operation
    parameters = check.operation_params
    if check.operator in {
        "revision_consistency",
        "shop_verification",
        "highlights_holder",
        "highlights_document_type",
    }:
        operation_name = check.operator
        parameters = (
            {"control": str(check.expected)}
            if check.operator == "revision_consistency"
            else {}
        )
    if not operation_name:
        raise ValueError("client_operation check requires an operation name")
    operation_registry = ctx.client_operations or {}
    operation = operation_registry.get(operation_name)
    if operation is None:
        raise ValueError(f"unknown client operation: {operation_name}")
    operation_context = ClientOperationContext(
        runtime=ctx,
        check=check,
        targets=tuple(targets),
    )
    result = operation.execute(operation_context, parameters)
    if result.inconclusive_pages:
        ctx.inconclusive_pages[rule_id] = result.inconclusive_pages
    target = next(
        (item for item in targets if result.page is not None and item.raw_page == result.page),
        targets[0],
    )
    observed = result.observed if result.observed is not None else result.original
    expected = result.expected if result.expected is not None else result.proposed
    return result.status, target, observed, expected


def client_operation_suggestions(
    check: Check,
    targets: list[_TextTarget],
    ctx: _EvalContext,
) -> list[OperationResult]:
    operation_name = check.operation
    parameters = check.operation_params
    if check.operator in {
        "revision_consistency",
        "shop_verification",
        "highlights_holder",
        "highlights_document_type",
    }:
        operation_name = check.operator
        parameters = (
            {"control": str(check.expected)}
            if check.operator == "revision_consistency"
            else {}
        )
    if not operation_name:
        raise ValueError("client_operation check requires an operation name")
    operation_registry = ctx.client_operations or {}
    operation = operation_registry.get(operation_name)
    if operation is None:
        raise ValueError(f"unknown client operation: {operation_name}")
    if operation.suggestions is None:
        return []
    operation_context = ClientOperationContext(
        runtime=ctx,
        check=check,
        targets=tuple(targets),
    )
    return operation.suggestions(operation_context, parameters)


def extract_year(value: str) -> str:
    """Extract the last year from a copyright or revision-date value."""
    four_digit = re.findall(r"\d{4}", value)
    if four_digit:
        return four_digit[-1]
    two_digit = re.findall(r"(?<!\d)\d{2}(?!\d)", value)
    if two_digit:
        year = int(two_digit[-1])
        return str((2000 if year < 50 else 1900) + year)
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
    present = bool(value) and (
        any(str(item).strip() for item in value)
        if isinstance(value, list)
        else bool(str(value).strip())
    )
    return present if condition.state == "present" else not present


def resolve_meta_value(field: str, document: Any | None) -> str | list[str] | None:
    if field == "meta_first_pnr_number":
        pnr_numbers = resolve_meta_value("meta_pnr_number", document)
        if isinstance(pnr_numbers, list):
            return pnr_numbers[0] if pnr_numbers else None
        return pnr_numbers
    if document is None:
        return None
    metadata = getattr(document, "client_metadata", None)
    value = metadata.get(field) if isinstance(metadata, Mapping) and field in metadata else getattr(
        document,
        field,
        None,
    )
    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
        return values or None
    if value is not None and str(value).strip():
        return str(value).strip()
    return None


def resolve_field_ref(
    ref: FieldRef,
    ctx: _EvalContext,
) -> tuple[_TextTarget | None, str | list[str] | None]:
    if ref.source == "document_meta":
        raw = resolve_meta_value(ref.field, ctx.document)
        if isinstance(raw, list):
            return None, [normalize(value, ref.normalization) for value in raw]
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
        raw = field_value(ref.field, target.text, target.page, ctx.client_entities)
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
        pattern = compile_user_regex(resolved_pattern)
    except UserRegexPatternError:
        return "INCONCLUSIVE", values[0][0], None, expected

    first_match: tuple[_TextTarget, re.Match[str]] | None = None
    for target, value in values:
        text = value or ""
        try:
            matches = list(pattern.finditer(text, timeout=USER_REGEX_TIMEOUT_SECONDS))
        except TimeoutError:
            _logger.warning("compiled_regex_timeout", rule_id=rule_id, page=target.page)
            return "INCONCLUSIVE", target, None, expected
        _logger.info(
            "compiled_regex_evaluated",
            rule_id=rule_id,
            page=target.page,
            match_count=len(matches),
        )
        if matches and first_match is None:
            first_match = (target, matches[0])

    if check.operator == "regex":
        if first_match is not None:
            target, match = first_match
            return "FAIL", target, match.group(0), expected
        return "PASS", values[0][0], None, expected
    if check.require_all:
        try:
            missing_target = next(
                (
                    target
                    for target, _value in values
                    if not pattern.search(_value or "", timeout=USER_REGEX_TIMEOUT_SECONDS)
                ),
                None,
            )
        except TimeoutError:
            return "INCONCLUSIVE", values[0][0], None, expected
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
    from app.core.compiled_rule_runtime import _CONTEXT_TOKEN_RE

    context_fields: list[str] = []
    missing_context: list[str] = []

    def replace_token(match: re.Match[str]) -> str:
        field = match.group(1)
        if field not in context_fields:
            context_fields.append(field)
        raw = resolve_meta_value(field, ctx.document)
        if raw is None:
            missing_context.append(field)
            return match.group(0)
        if isinstance(raw, list):
            return "(?:" + "|".join(re.escape(item) for item in raw) + ")"
        escaped = re.escape(raw)
        if field == "meta_first_pnr_number":
            escaped = escaped.replace(r"\-", r"\s*-\s*")
        return escaped

    resolved = _CONTEXT_TOKEN_RE.sub(replace_token, pattern)
    return resolved, context_fields, sorted(set(missing_context))


def resolve_replacement_template(template: str | None, document: Any | None) -> str | None:
    from app.core.compiled_rule_runtime import _CONTEXT_TOKEN_RE

    if template is None:
        return None
    missing_context = False

    def replace_token(match: re.Match[str]) -> str:
        nonlocal missing_context
        token = match.group(1)
        if token == "temperature_fahrenheit":
            return match.group(0)
        value = resolve_meta_value(token, document)
        if value is None:
            missing_context = True
            return match.group(0)
        if isinstance(value, list):
            if len(value) != 1:
                missing_context = True
                return match.group(0)
            value = value[0]
        return value.replace("\\", "\\\\")

    resolved = _CONTEXT_TOKEN_RE.sub(replace_token, template)
    return None if missing_context else resolved
