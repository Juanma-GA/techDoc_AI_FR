"""Deterministic suggestions and repairs for compiled rules."""

from __future__ import annotations

import difflib
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from app.checks.raw import RawSuggestion
from app.core.compiled_rules import Check, CompiledRule
from app.parsers.pdf_parser import ParsedPage

from app.core.compiled_rule_runtime import (
    _CONTEXT_TOKEN_RE,
    _BBox,
    _EvalContext,
    _TextTarget,
    document_metadata,
    first_bbox,
    is_nonzero_bbox,
    observed_bbox,
    suggestion_bbox,
)
from app.core.compiled_rule_operators import (
    FONT_SIZE_TOLERANCE,
    evaluate_check,
    field_value,
    matching_font_spans,
    normalize,
    pressure_conversion_issues,
    resolve_field_ref,
    resolve_regex_pattern,
    resolve_replacement_template,
    revision_findings,
)


_TEMPERATURE_FAHRENHEIT_REPLACEMENT = "{{temperature_fahrenheit}}"
_TEMPERATURE_CELSIUS_MATCH = re.compile(
    r"(?i)^(?P<prefix>temperature\s*:\s*)?"
    r"(?P<first>[+-]?\d+(?:[.,]\d+)?)"
    r"(?:\s+to\s+(?P<second>[+-]?\d+(?:[.,]\d+)?))?"
    r"\s+deg\.\s*C$"
)


def manual_suggestions(rule: CompiledRule, targets: list[_TextTarget]) -> list[RawSuggestion]:
    return [
        RawSuggestion(
            rule_kind="compiled_checklist" if rule.source == "user_checklist" else "compiled_standard",
            rule_code=rule.id,
            severity=rule.severity,
            message=f"Vérification manuelle requise : {rule.manual_instruction}",
            original="",
            proposed="",
            page=target.raw_page,
            span=(0, 0),
        )
        for target in targets
    ]


def deterministic_suggestions(
    rule: CompiledRule,
    targets: list[_TextTarget],
    result: Any,
    pdf_pages: list[ParsedPage] | None,
    ctx: _EvalContext,
) -> list[RawSuggestion]:
    rule_kind = "compiled_standard" if rule.source == "standard_rule" else "compiled_checklist"
    message = f"Règle non satisfaite : {rule.failure_message or rule.topic}"
    suggestions: list[RawSuggestion] = []
    has_non_repairable_check = False
    for check in rule.checks:
        if check.operator == "regex" and check.expected is not None:
            suggestions.extend(regex_suggestions(rule, check, targets, rule_kind, message, ctx))
        elif check.operator == "pressure_conversion":
            suggestions.extend(
                pressure_conversion_suggestions(
                    rule,
                    check,
                    targets,
                    rule_kind,
                    message,
                    ctx.pdf_pages,
                )
            )
        elif check.operator == "revision_consistency":
            suggestions.extend(
                revision_consistency_suggestions(rule, check, rule_kind, ctx)
            )
        elif check.operator == "regex_exists" and check.expected_display is not None:
            check_status, _target, _observed, _expected = evaluate_check(
                check, targets, ctx, rule.id
            )
            if check_status == "FAIL":
                suggestions.extend(
                    fuzzy_required_suggestions(
                        rule,
                        check,
                        targets,
                        rule_kind,
                        message,
                        ctx,
                    )
                )
        elif check.operator == "normalized_equals":
            if check.field == "important_notice":
                suggestions.extend(
                    important_notice_suggestions(
                        check, targets, rule.id, rule.severity, rule_kind, message, ctx.pdf_pages
                    )
                )
            else:
                suggestions.extend(
                    normalized_equals_suggestions(
                        check, targets, rule.id, rule.severity, rule_kind, message, ctx.pdf_pages
                    )
                )
        elif check.operator == "equals_field":
            suggestions.extend(
                equals_field_suggestions(
                    check, targets, rule.id, rule.severity, rule_kind, message, ctx
                )
            )
        elif check.operator == "contains_none" and isinstance(check.expected, list):
            suggestions.extend(
                term_search_suggestions(
                    rule,
                    targets,
                    [str(term) for term in check.expected],
                    check.replacement,
                    check.replacements,
                    rule_kind,
                    message,
                    ctx.pdf_pages,
                )
            )
        elif check.operator == "not_exists" and isinstance(check.expected, str):
            suggestions.extend(
                term_search_suggestions(
                    rule,
                    targets,
                    [check.expected],
                    check.replacement,
                    None,
                    rule_kind,
                    message,
                    ctx.pdf_pages,
                )
            )
        elif check.operator == "font_size_equals":
            suggestions.extend(
                font_size_suggestions(
                    rule,
                    check,
                    targets,
                    rule_kind,
                    message,
                )
            )
            has_non_repairable_check = True

    if suggestions:
        target_order = {target.raw_page: index for index, target in enumerate(targets)}
        suggestions.sort(
            key=lambda item: (target_order.get(item.page, len(targets)), item.span[0])
        )
        return suggestions

    if has_non_repairable_check:
        return []

    if not result.evidence.observed_value:
        fallback_target = next(
            (target for target in targets if target.page == result.evidence.page),
            targets[0],
        )
        expected = expected_display(rule, result.evidence.expected_value, ctx.document)
        detail = f" Element attendu : {expected}" if expected else " Element attendu absent de la page"
        missing_bbox = missing_item_bbox(rule, fallback_target, expected, pdf_pages)
        return [
            RawSuggestion(
                rule_kind=rule_kind,
                rule_code=rule.id,
                severity=rule.severity,
                message=f"{message}{detail}",
                original="",
                proposed=expected or "",
                page=fallback_target.raw_page,
                span=(0, 0),
                bbox=missing_bbox,
            )
        ]

    fallback_target = next(
        (target.raw_page for target in targets if target.page == result.evidence.page),
        targets[0].raw_page,
    )
    fallback_target = next(
        (target for target in targets if target.raw_page == fallback_target),
        targets[0],
    )
    observed = result.evidence.observed_value or ""
    return [
        RawSuggestion(
            rule_kind=rule_kind,
            rule_code=rule.id,
            severity=rule.severity,
            message=message,
            original=observed,
            proposed=result.evidence.expected_value or "",
            page=fallback_target.raw_page,
                span=(0, len(observed)),
                bbox=suggestion_bbox(fallback_target, observed, pdf_pages),
        )
    ]


def revision_consistency_suggestions(
    rule: CompiledRule,
    check: Check,
    rule_kind: str,
    ctx: _EvalContext,
) -> list[RawSuggestion]:
    """One suggestion per page/subject where the three sources diverge."""
    text_by_page = {target.raw_page: target.text for target in ctx.all_targets}
    suggestions: list[RawSuggestion] = []
    for finding in revision_findings(check, ctx):
        start = text_by_page.get(finding.page, "").find(finding.original)
        suggestions.append(
            RawSuggestion(
                rule_kind=rule_kind,
                rule_code=rule.id,
                severity=rule.severity,
                message=finding.message,
                original=finding.original,
                proposed=finding.proposed,
                page=finding.page,
                span=(start, start + len(finding.original)) if start >= 0 else (0, 0),
                bbox=finding.bbox,
            )
        )
    return suggestions


def font_size_suggestions(
    rule: CompiledRule,
    check: Check,
    targets: list[_TextTarget],
    rule_kind: str,
    message: str,
) -> list[RawSuggestion]:
    """Emit a localized detection-only finding for each wrong font size."""
    expected_size = float(check.expected)
    suggestions: list[RawSuggestion] = []
    for target in targets:
        for start, end, original, bbox, observed_size, _font in matching_font_spans(check, target):
            if abs(observed_size - expected_size) <= FONT_SIZE_TOLERANCE:
                continue
            suggestions.append(
                RawSuggestion(
                    rule_kind=rule_kind,
                    rule_code=rule.id,
                    severity=rule.severity,
                    message=(
                        f"{message} Taille detectee : {observed_size:.0f} pt. "
                        f"Taille attendue : {expected_size:g} pt."
                    ),
                    original=original,
                    proposed="",
                    page=target.raw_page,
                    span=(start, end),
                    bbox=bbox,
                )
            )
    return suggestions


def fuzzy_required_suggestions(
    rule: CompiledRule,
    check: Check,
    targets: list[_TextTarget],
    rule_kind: str,
    message: str,
    ctx: _EvalContext,
) -> list[RawSuggestion]:
    """Suggest minimal edits when a required canonical value is nearly present."""
    if check.expected_display is None:
        return []
    expected = resolve_display_template(check.expected_display, ctx.document)
    if not expected:
        return []

    suggestions: list[RawSuggestion] = []
    expected_compact = " ".join(expected.split())
    expected_folded = expected_compact.casefold()
    for target in targets:
        candidates = candidate_ranges(target)
        if not candidates:
            continue
        scored = []
        for raw_candidate, raw_start, _raw_end in candidates:
            candidate, start = _candidate_content(raw_candidate, raw_start)
            candidate_compact = " ".join(candidate.split())
            if not candidate_compact:
                continue
            candidate_folded = candidate_compact.casefold()
            if check.suggestion_mode == "all" and expected_folded in candidate_folded:
                continue
            if check.missing_anchor_position == "below":
                expected_label = expected_compact.split(":", 1)[0].strip()
                if expected_label and not candidate_folded.startswith(expected_label.casefold()):
                    continue
            ratio = difflib.SequenceMatcher(
                None,
                candidate_folded,
                expected_folded,
                autojunk=False,
            ).ratio()
            is_expected_prefix = expected_folded.startswith(candidate_folded)
            if not is_expected_prefix and ratio < required_repair_threshold(len(expected_compact)):
                continue
            if is_expected_prefix and len(candidate_compact) < max(8, len(expected_compact) // 3):
                continue
            scored.append((ratio, candidate, start, start + len(candidate)))
        if not scored:
            continue
        scored.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
        if check.suggestion_mode == "all":
            selected: list[tuple[float, str, int, int]] = []
            for candidate in scored:
                _ratio, _text, start, end = candidate
                if any(start < selected_end and end > selected_start for _, _, selected_start, selected_end in selected):
                    continue
                selected.append(candidate)
            for _ratio, candidate, start, end in sorted(selected, key=lambda item: item[2]):
                raw_candidate = candidate
                candidate = candidate.strip()
                leading_whitespace = len(raw_candidate) - len(raw_candidate.lstrip())
                candidate_start = start + leading_whitespace
                suggestions.append(
                    RawSuggestion(
                        rule_kind=rule_kind,
                        rule_code=rule.id,
                        severity=rule.severity,
                        message=message,
                        original=candidate,
                        proposed=expected,
                        page=target.raw_page,
                        span=(candidate_start, candidate_start + len(candidate)),
                        bbox=suggestion_bbox(
                            target,
                            candidate,
                            ctx.pdf_pages,
                            span_start=candidate_start,
                        ),
                    )
                )
            continue
        _ratio, candidate, start, end = scored[0]
        if check.suggestion_mode == "single":
            candidate = candidate.strip()
            leading_whitespace = len(scored[0][1]) - len(scored[0][1].lstrip())
            candidate_start = start + leading_whitespace
            suggestions.append(
                RawSuggestion(
                    rule_kind=rule_kind,
                    rule_code=rule.id,
                    severity=rule.severity,
                    message=message,
                    original=candidate,
                    proposed=expected,
                    page=target.raw_page,
                    span=(candidate_start, candidate_start + len(candidate)),
                    bbox=suggestion_bbox(
                        target,
                        candidate,
                        ctx.pdf_pages,
                        span_start=candidate_start,
                    ),
                )
            )
            continue
        suggestions.extend(
            minimal_diff_suggestions(
                rule,
                candidate.rstrip(),
                expected,
                start,
                target,
                rule_kind,
                message,
                ctx.pdf_pages,
            )
        )
    return suggestions


def required_repair_threshold(expected_length: int) -> float:
    if expected_length <= 12:
        return 0.70
    if expected_length <= 24:
        return 0.62
    return 0.55


def candidate_ranges(target: _TextTarget) -> list[tuple[str, int, int]]:
    """Return line-like candidates with offsets in the scoped target text."""
    line_ranges: list[tuple[str, int, int]]
    if target.span_ranges:
        grouped: list[tuple[int, int, float]] = []
        for start, end, bbox, _size, _font in sorted(target.span_ranges, key=lambda item: item[0]):
            center_y = (bbox[1] + bbox[3]) / 2
            if grouped and abs(center_y - grouped[-1][2]) <= 3.0:
                grouped[-1] = (grouped[-1][0], end, grouped[-1][2])
            else:
                grouped.append((start, end, center_y))
        line_ranges = [
            (target.text[start:end], start, end)
            for start, end, _center_y in grouped
            if target.text[start:end].strip()
        ]
    else:
        line_ranges = []
        cursor = 0
        for line in target.text.splitlines() or [target.text]:
            start = target.text.find(line, cursor)
            if start < 0:
                continue
            end = start + len(line)
            cursor = end
            if line.strip():
                line_ranges.append((line, start, end))

    candidates = list(line_ranges)
    for window_size in range(2, min(4, len(line_ranges)) + 1):
        for index in range(len(line_ranges) - window_size + 1):
            start = line_ranges[index][1]
            end = line_ranges[index + window_size - 1][2]
            candidate = target.text[start:end]
            if candidate and (candidate, start, end) not in candidates:
                candidates.append((candidate, start, end))
    for line, line_start, _line_end in line_ranges:
        words = list(re.finditer(r"\S+", line))
        for window_size in range(1, min(6, len(words)) + 1):
            for index in range(len(words) - window_size + 1):
                start = line_start + words[index].start()
                end = line_start + words[index + window_size - 1].end()
                candidate = target.text[start:end]
                if candidate and (candidate, start, end) not in candidates:
                    candidates.append((candidate, start, end))
    return candidates


def _candidate_content(candidate: str, start: int) -> tuple[str, int]:
    leading_whitespace = len(candidate) - len(candidate.lstrip())
    start += leading_whitespace
    candidate = candidate[leading_whitespace:]
    marker = re.match(r"[-*]\s+", candidate)
    if marker is not None:
        start += marker.end()
        candidate = candidate[marker.end() :]
    return candidate.rstrip(), start


def minimal_diff_suggestions(
    rule: CompiledRule,
    candidate: str,
    expected: str,
    candidate_start: int,
    target: _TextTarget,
    rule_kind: str,
    message: str,
    pdf_pages: list[ParsedPage] | None,
) -> list[RawSuggestion]:
    candidate = candidate.strip()
    if not candidate:
        return []
    candidate_tokens = list(re.finditer(r"\S+", candidate))
    expected_tokens = list(re.finditer(r"\S+", expected))
    if len(candidate_tokens) > 1 and len(expected_tokens) > 1:
        return word_diff_suggestions(
            rule,
            candidate,
            expected,
            candidate_start,
            target,
            rule_kind,
            message,
            pdf_pages,
        )
    matcher = difflib.SequenceMatcher(
        None,
        candidate.casefold(),
        expected.casefold(),
        autojunk=False,
    )
    suggestions: list[RawSuggestion] = []
    edits = [
        (start, end, expected_start, expected_end)
        for tag, start, end, expected_start, expected_end in matcher.get_opcodes()
        if tag != "equal"
    ]
    merged_edits: list[tuple[int, int, int, int]] = []
    for edit in edits:
        if merged_edits:
            previous = merged_edits[-1]
            if edit[0] - previous[1] <= 1 and edit[2] - previous[3] <= 1:
                merged_edits[-1] = (previous[0], edit[1], previous[2], edit[3])
                continue
        merged_edits.append(edit)
    for start, end, expected_start, expected_end in merged_edits:
        original = candidate[start:end]
        proposed = expected[expected_start:expected_end]
        absolute_start = candidate_start + start
        bbox_text = original or candidate
        bbox_start = absolute_start if original else candidate_start
        suggestions.append(
            RawSuggestion(
                rule_kind=rule_kind,
                rule_code=rule.id,
                severity=rule.severity,
                message=message,
                original=original,
                proposed=proposed,
                page=target.raw_page,
                span=(absolute_start, absolute_start + len(original)),
                bbox=suggestion_bbox(
                    target,
                    bbox_text,
                    pdf_pages,
                    span_start=bbox_start,
                ),
            )
        )
    return suggestions


def word_diff_suggestions(
    rule: CompiledRule,
    candidate: str,
    expected: str,
    candidate_start: int,
    target: _TextTarget,
    rule_kind: str,
    message: str,
    pdf_pages: list[ParsedPage] | None,
) -> list[RawSuggestion]:
    candidate_tokens = list(re.finditer(r"\S+", candidate))
    expected_tokens = list(re.finditer(r"\S+", expected))
    matcher = difflib.SequenceMatcher(
        None,
        [token.group().casefold() for token in candidate_tokens],
        [token.group().casefold() for token in expected_tokens],
        autojunk=False,
    )
    suggestions: list[RawSuggestion] = []

    def add_suggestion(original: str, proposed: str, absolute_start: int) -> None:
        if not original and not proposed:
            return
        bbox_text = original or candidate
        bbox_start = absolute_start if original else candidate_start
        suggestions.append(
            RawSuggestion(
                rule_kind=rule_kind,
                rule_code=rule.id,
                severity=rule.severity,
                message=message,
                original=original,
                proposed=proposed,
                page=target.raw_page,
                span=(absolute_start, absolute_start + len(original)),
                bbox=suggestion_bbox(
                    target,
                    bbox_text,
                    pdf_pages,
                    span_start=bbox_start,
                ),
            )
        )

    for tag, start, end, expected_start, expected_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        pair_count = min(end - start, expected_end - expected_start)
        for offset in range(pair_count):
            candidate_token = candidate_tokens[start + offset]
            expected_token = expected_tokens[expected_start + offset]
            original_token = candidate_token.group()
            proposed_token = expected_token.group()
            original_word = re.fullmatch(
                r"(?P<prefix>\W*)(?P<word>[^\W\d_]+)(?P<suffix>\W*)",
                original_token,
            )
            proposed_word = re.fullmatch(
                r"(?P<prefix>\W*)(?P<word>[^\W\d_]+)(?P<suffix>\W*)",
                proposed_token,
            )
            if original_word and proposed_word:
                add_suggestion(
                    original_word.group("word"),
                    proposed_word.group("word"),
                    candidate_start
                    + candidate_token.start()
                    + len(original_word.group("prefix")),
                )
                continue
            prefix = 0
            while (
                prefix < len(original_token)
                and prefix < len(proposed_token)
                and original_token[prefix].casefold() == proposed_token[prefix].casefold()
            ):
                prefix += 1
            suffix = 0
            while (
                suffix < len(original_token) - prefix
                and suffix < len(proposed_token) - prefix
                and original_token[-suffix - 1].casefold()
                == proposed_token[-suffix - 1].casefold()
            ):
                suffix += 1
            original = original_token[prefix : len(original_token) - suffix or None]
            proposed = proposed_token[prefix : len(proposed_token) - suffix or None]
            add_suggestion(
                original,
                proposed,
                candidate_start + candidate_token.start() + prefix,
            )

        if end - start > pair_count:
            first = candidate_tokens[start + pair_count]
            last = candidate_tokens[end - 1]
            add_suggestion(
                candidate[first.start() : last.end()],
                "",
                candidate_start + first.start(),
            )
        if expected_end - expected_start > pair_count:
            first = expected_tokens[expected_start + pair_count]
            last = expected_tokens[expected_end - 1]
            insertion_start = expected_tokens[expected_start - 1].end() if expected_start else 0
            add_suggestion(
                "",
                expected[insertion_start : last.end()],
                candidate_start + (candidate_tokens[start - 1].end() if start else 0),
            )
    return suggestions


def expected_display(rule: CompiledRule, expected: str | None, document: Any | None) -> str | None:
    for check in rule.checks:
        if check.expected_display is None:
            continue
        if expected is None or str(check.expected) == expected:
            return resolve_display_template(check.expected_display, document)
    return None


def resolve_display_template(template: str, document: Any | None) -> str:
    metadata = document_metadata(document)

    def replace_token(match: re.Match[str]) -> str:
        return metadata.get(match.group(1), match.group(0))

    return _CONTEXT_TOKEN_RE.sub(replace_token, template)


def missing_item_bbox(
    rule: CompiledRule,
    target: _TextTarget,
    expected: str | None,
    pdf_pages: list[ParsedPage] | None,
) -> _BBox:
    for check in rule.checks:
        if not check.missing_anchor:
            continue
        try:
            match = re.search(check.missing_anchor, target.text)
        except re.error:
            match = None
        if match is None:
            continue
        anchor = observed_bbox(
            target,
            match.group(0),
            pdf_pages,
            span_start=match.start(),
        )
        if not is_nonzero_bbox(anchor):
            continue
        if check.missing_anchor_position == "same":
            return anchor
        height = max(anchor[3] - anchor[1], 1.0)
        width = max(anchor[2] - anchor[0], height * max(len(expected or ""), 4) * 0.45)
        right_edges = [anchor[2]]
        if target.bbox is not None:
            right_edges.append(target.bbox[2])
        right_edges.extend(bbox[2] for _start, _end, bbox, _size, _font in target.span_ranges)
        if pdf_pages is not None:
            page = next((item for item in pdf_pages if item.page == target.raw_page), None)
            if page is not None:
                right_edges.extend(span.bbox[2] for span in page.spans)
        max_right = max(right_edges)
        width = min(width, max(max_right - anchor[0], anchor[2] - anchor[0]))
        if check.missing_anchor_position == "below":
            top = anchor[3] + height * 0.15
            bottom = anchor[3] + height * 1.35
        else:
            top = max(0.0, anchor[1] - height * 1.35)
            bottom = max(0.0, anchor[1] - height * 0.15)
        return (anchor[0], top, anchor[0] + width, bottom)
    return first_bbox(target)


def normalized_equals_suggestions(
    check: Check,
    targets: list[_TextTarget],
    rule_id: str,
    severity: str,
    rule_kind: str,
    message: str,
    pdf_pages: list[ParsedPage] | None,
) -> list[RawSuggestion]:
    expected = normalize(
        str(check.expected) if check.expected is not None else "",
        check.normalization,
    )
    suggestions: list[RawSuggestion] = []
    for target in targets:
        raw_value = field_value(check.field, target.text, target.page)
        if not raw_value:
            continue
        observed = normalize(raw_value, check.normalization)
        if observed == expected:
            continue
        start = target.text.find(raw_value)
        if start < 0:
            start = 0
        suggestions.append(
            RawSuggestion(
                rule_kind=rule_kind,
                rule_code=rule_id,
                severity=severity,
                message=message,
                original=raw_value,
                proposed=expected,
                page=target.raw_page,
                span=(start, start + len(raw_value)),
                bbox=suggestion_bbox(target, raw_value, pdf_pages, span_start=start),
            )
        )
    return suggestions


def important_notice_suggestions(
    check: Check,
    targets: list[_TextTarget],
    rule_id: str,
    severity: str,
    rule_kind: str,
    message: str,
    pdf_pages: list[ParsedPage] | None,
) -> list[RawSuggestion]:
    """Emit paragraph-level suggestions for an incorrect legal notice."""
    expected = normalize(
        str(check.expected) if check.expected is not None else "",
        check.normalization,
    )
    suggestions: list[RawSuggestion] = []
    for target in targets:
        raw_value = field_value(check.field, target.text, target.page)
        observed = normalize(raw_value, check.normalization) if raw_value else ""
        if observed == expected:
            continue
        if not raw_value:
            suggestions.append(
                RawSuggestion(
                    rule_kind=rule_kind,
                    rule_code=rule_id,
                    severity=severity,
                    message=f"{message} Texte attendu absent : {expected}",
                    original="",
                    proposed=expected,
                    page=target.raw_page,
                    span=(0, 0),
                    bbox=first_bbox(target),
                )
            )
            continue

        suggestions.extend(
            _important_notice_diff_suggestions(
                expected,
                raw_value,
                target,
                rule_id,
                severity,
                rule_kind,
                message,
                pdf_pages,
            )
        )
    return suggestions


def _important_notice_diff_suggestions(
    expected: str,
    raw_value: str,
    target: _TextTarget,
    rule_id: str,
    severity: str,
    rule_kind: str,
    message: str,
    pdf_pages: list[ParsedPage] | None,
) -> list[RawSuggestion]:
    expected_tokens = expected.split()
    observed_tokens = raw_value.split()
    raw_token_matches = list(re.finditer(r"\S+", raw_value))
    raw_start = target.text.find(raw_value)
    if raw_start < 0:
        raw_start = 0
    matcher = difflib.SequenceMatcher(
        None,
        observed_tokens,
        expected_tokens,
        autojunk=False,
    )
    suggestions: list[RawSuggestion] = []
    for tag, observed_start, observed_end, expected_start, expected_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        expected_fragment = " ".join(expected_tokens[expected_start:expected_end])
        if observed_start < observed_end and raw_token_matches:
            raw_fragment_start = raw_token_matches[min(observed_start, len(raw_token_matches) - 1)].start()
            raw_fragment_end = raw_token_matches[observed_end - 1].end()
            original = raw_value[raw_fragment_start:raw_fragment_end]
            absolute_start = raw_start + raw_fragment_start
            bbox = suggestion_bbox(
                target,
                original,
                pdf_pages,
                span_start=absolute_start,
            )
        else:
            original = ""
            absolute_start = raw_start + (
                raw_token_matches[observed_start].start()
                if observed_start < len(raw_token_matches)
                else len(raw_value)
            )
            bbox = _insertion_bbox(target, absolute_start)

        if tag == "insert":
            detail = f"Texte manquant : {expected_fragment}"
            proposed = expected_fragment
        elif tag == "replace":
            detail = f"Texte attendu : {expected_fragment}"
            proposed = expected_fragment
        else:
            detail = f"Texte en trop : {original}"
            proposed = ""
        suggestions.append(
            RawSuggestion(
                rule_kind=rule_kind,
                rule_code=rule_id,
                severity=severity,
                message=f"{message} {detail}",
                original=original,
                proposed=proposed,
                page=target.raw_page,
                span=(absolute_start, absolute_start + len(original)),
                bbox=bbox,
            )
        )
    return suggestions


def _insertion_bbox(target: _TextTarget, offset: int) -> _BBox:
    """Return the whitespace gap around a missing text insertion when possible."""
    previous = [item for item in target.span_ranges if item[1] <= offset]
    following = [item for item in target.span_ranges if item[0] >= offset]
    previous_item = previous[-1] if previous else None
    following_item = following[0] if following else None
    if previous_item is not None and following_item is not None:
        previous_bbox = previous_item[2]
        following_bbox = following_item[2]
        if following_bbox[1] >= previous_bbox[3]:
            return (
                min(previous_bbox[0], following_bbox[0]),
                previous_bbox[3],
                max(previous_bbox[2], following_bbox[2]),
                following_bbox[1],
            )
    if following_item is not None:
        return following_item[2]
    if previous_item is not None:
        return previous_item[2]
    return first_bbox(target)


def equals_field_suggestions(
    check: Check,
    targets: list[_TextTarget],
    rule_id: str,
    severity: str,
    rule_kind: str,
    message: str,
    ctx: _EvalContext,
) -> list[RawSuggestion]:
    if check.compare_to is None:
        return []
    _right_target, right_value = resolve_field_ref(check.compare_to, ctx)
    if right_value is None:
        return []

    suggestions: list[RawSuggestion] = []
    for target in targets:
        raw_value = field_value(check.field, target.text, target.page)
        if not raw_value:
            continue
        observed = normalize(raw_value, check.normalization)
        if observed == right_value:
            continue
        start = target.text.find(raw_value)
        if start < 0:
            start = 0
        suggestions.append(
            RawSuggestion(
                rule_kind=rule_kind,
                rule_code=rule_id,
                severity=severity,
                message=message,
                original=raw_value,
                proposed=right_value,
                page=target.raw_page,
                span=(start, start + len(raw_value)),
                bbox=suggestion_bbox(target, raw_value, ctx.pdf_pages, span_start=start),
            )
        )
    return suggestions


def regex_suggestions(
    rule: CompiledRule,
    check: Check,
    targets: list[_TextTarget],
    rule_kind: str,
    message: str,
    ctx: _EvalContext,
) -> list[RawSuggestion]:
    resolved_pattern, _context_fields, missing_context = resolve_regex_pattern(
        str(check.expected), ctx
    )
    if missing_context:
        return []
    try:
        matches = [
            (target, match)
            for target in targets
            for match in re.finditer(resolved_pattern, target.text)
            if match.group(0)
        ]
    except re.error:
        return []
    suggestions: list[RawSuggestion] = []
    replacement = resolve_replacement_template(check.replacement, ctx.document)
    for target, match in matches:
        original = match.group(0)
        proposed = ""
        if replacement is not None:
            if replacement == _TEMPERATURE_FAHRENHEIT_REPLACEMENT:
                proposed = _temperature_fahrenheit_replacement(original)
            else:
                try:
                    proposed = match.expand(replacement)
                except re.error:
                    proposed = replacement
        suggestions.append(
            RawSuggestion(
                rule_kind=rule_kind,
                rule_code=rule.id,
                severity=rule.severity,
                message=message,
                original=original,
                proposed=proposed,
                page=target.raw_page,
                span=match.span(),
                bbox=suggestion_bbox(
                    target,
                    original,
                    ctx.pdf_pages,
                    span_start=match.start(),
                ),
            )
        )
    return suggestions


def _temperature_fahrenheit_replacement(original: str) -> str:
    match = _TEMPERATURE_CELSIUS_MATCH.fullmatch(original)
    if match is None:
        return ""

    def convert(value: str) -> str:
        celsius = Decimal(value.replace(",", "."))
        fahrenheit = (celsius * Decimal(9) / Decimal(5) + Decimal(32)).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        if fahrenheit == fahrenheit.to_integral():
            return str(int(fahrenheit))
        return format(fahrenheit, "f").rstrip("0").rstrip(".")

    try:
        first = convert(match.group("first"))
        second_value = match.group("second")
        second = f" to {convert(second_value)}" if second_value else ""
    except (InvalidOperation, ValueError):
        return ""
    return f"{original} ({first}{second} deg. F)"


def pressure_conversion_suggestions(
    rule: CompiledRule,
    check: Check,
    targets: list[_TextTarget],
    rule_kind: str,
    message: str,
    pdf_pages: list[ParsedPage] | None,
) -> list[RawSuggestion]:
    suggestions: list[RawSuggestion] = []
    for target in targets:
        for issue in pressure_conversion_issues(target.text, str(check.expected)):
            suggestions.append(
                RawSuggestion(
                    rule_kind=rule_kind,
                    rule_code=rule.id,
                    severity=rule.severity,
                    message=message,
                    original=issue.original,
                    proposed=issue.proposed,
                    page=target.raw_page,
                    span=issue.span,
                    bbox=suggestion_bbox(
                        target,
                        issue.original,
                        pdf_pages,
                        span_start=issue.span[0],
                    ),
                )
            )
    return suggestions


def term_search_suggestions(
    rule: CompiledRule,
    targets: list[_TextTarget],
    terms: list[str],
    replacement: str | None,
    replacements: dict[str, str] | None,
    rule_kind: str,
    message: str,
    pdf_pages: list[ParsedPage] | None,
) -> list[RawSuggestion]:
    suggestions: list[RawSuggestion] = []
    for target in targets:
        text = target.text
        for term in terms:
            if not term:
                continue
            start = 0
            while True:
                idx = text.find(term, start)
                if idx < 0:
                    break
                proposed = (replacements or {}).get(term, replacement or "")
                suggestions.append(
                    RawSuggestion(
                        rule_kind=rule_kind,
                        rule_code=rule.id,
                        severity=rule.severity,
                        message=message,
                        original=term,
                        proposed=proposed,
                        page=target.raw_page,
                        span=(idx, idx + len(term)),
                        bbox=suggestion_bbox(target, term, pdf_pages, span_start=idx),
                    )
                )
                start = idx + len(term)
    return suggestions
