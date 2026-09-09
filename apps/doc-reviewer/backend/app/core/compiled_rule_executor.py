"""Deterministic execution for the strict CompiledRule vocabulary."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy.orm import Session

from app.checks.raw import RawSuggestion
from app.core.compiled_rules import (
    Check,
    CompiledRule,
    DocxEvidenceLocation,
    Evidence,
    PdfEvidenceLocation,
    RuleResult,
)
from app.core.errors import AppError
from app.core.llm_suggester import call_chat
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


_SEMANTIC_GROUP_CHAR_LIMIT = 10_000
_SEMANTIC_TOTAL_CHAR_LIMIT = 120_000


def execute_pdf_rules(
    parsed: ParsedPdf,
    rules: list[CompiledRule],
    db: Session | None = None,
) -> tuple[list[RuleResult], list[RawSuggestion]]:
    targets = [
        _TextTarget(page=str(page.page), text=page.text, raw_page=page.page)
        for page in parsed.pages
    ]
    return _execute(rules, targets, parsed.pages, is_docx=False, db=db)


def execute_docx_rules(
    blocks: list[Block],
    rules: list[CompiledRule],
    db: Session | None = None,
) -> tuple[list[RuleResult], list[RawSuggestion]]:
    targets = [
        _TextTarget(
            page=str(block.page),
            text=block.text,
            raw_page=block.index,
            target_id=block.target_id,
        )
        for block in blocks
    ]
    return _execute(rules, targets, None, is_docx=True, blocks=blocks, db=db)


def _execute(
    rules: list[CompiledRule],
    targets: list[_TextTarget],
    pdf_pages: list[ParsedPage] | None,
    *,
    is_docx: bool,
    blocks: list[Block] | None = None,
    db: Session | None = None,
) -> tuple[list[RuleResult], list[RawSuggestion]]:
    results: list[RuleResult] = []
    raws: list[RawSuggestion] = []
    for rule in rules:
        scoped = _scope_targets(rule, targets, is_docx=is_docx, blocks=blocks, pdf_pages=pdf_pages)
        if rule.execution == "semantic":
            result, semantic_raws = _execute_semantic(rule, scoped or [], db, is_docx, pdf_pages)
            results.append(result)
            raws.extend(semantic_raws)
            continue
        if rule.execution == "manual":
            results.append(RuleResult(rule_id=rule.id, status="MANUAL"))
            raws.extend(_manual_suggestions(rule, scoped or targets))
            continue
        if rule.execution == "unsupported":
            results.append(RuleResult(rule_id=rule.id, status="UNSUPPORTED"))
            continue
        if scoped is None or not scoped:
            evidence = _evidence(targets[0] if targets else None, None, None, is_docx, pdf_pages)
            results.append(RuleResult(rule_id=rule.id, status="INCONCLUSIVE", evidence=evidence))
            continue
        result = _evaluate_rule(rule, scoped, is_docx, pdf_pages)
        results.append(result)
        if result.status == "FAIL" and result.evidence is not None:
            raws.extend(_deterministic_suggestions(rule, scoped, result, is_docx, pdf_pages))
    return results, raws


def _scope_targets(
    rule: CompiledRule,
    targets: list[_TextTarget],
    *,
    is_docx: bool,
    blocks: list[Block] | None,
    pdf_pages: list[ParsedPage] | None,
) -> list[_TextTarget] | None:
    scoped = targets if rule.target.page == "all" else [target for target in targets if target.page == rule.target.page]
    if rule.target.region == "full_page":
        return scoped
    if is_docx:
        if blocks is None:
            return None
        allowed_ids = {block.target_id for block in blocks if block.zone == rule.target.region}
        return [target for target in scoped if target.target_id in allowed_ids]
    if pdf_pages is None:
        return None
    pages_by_number = {page.page: page for page in pdf_pages}
    selected: list[_TextTarget] = []
    for target in scoped:
        page = pages_by_number.get(target.raw_page)
        if page is None or not page.spans:
            continue
        min_y = min(span.bbox[1] for span in page.spans)
        max_y = max(span.bbox[3] for span in page.spans)
        height = max_y - min_y
        if height <= 0:
            continue
        if rule.target.region == "header":
            spans = [span for span in page.spans if span.bbox[1] <= min_y + height * 0.25]
        elif rule.target.region == "footer":
            spans = [span for span in page.spans if span.bbox[3] >= max_y - height * 0.25]
        else:
            spans = [
                span
                for span in page.spans
                if span.bbox[1] > min_y + height * 0.25
                and span.bbox[3] < max_y - height * 0.25
            ]
        if spans:
            selected.append(replace(target, text=" ".join(span.text.strip() for span in spans)))
    return selected or None


def _execute_semantic(
    rule: CompiledRule,
    targets: list[_TextTarget],
    db: Session | None,
    is_docx: bool,
    pdf_pages: list[ParsedPage] | None,
) -> tuple[RuleResult, list[RawSuggestion]]:
    fallback_target = targets[0] if targets else None
    if db is None or not targets:
        return (
            RuleResult(
                rule_id=rule.id,
                status="INCONCLUSIVE",
                evidence=_evidence(fallback_target, None, rule.semantic_instruction, is_docx, pdf_pages),
            ),
            [],
        )

    groups = _semantic_groups(targets)
    violations: list[tuple[_TextTarget, str, str, str]] = []
    failed_call = False
    for group in groups:
        payload = {
            "rule": rule.semantic_instruction,
            "topic": rule.topic,
            "pages": [{"page": target.page, "text": target.text} for target in group],
        }
        system = (
            "Tu es un contrôleur de conformité documentaire. Évalue uniquement la règle fournie "
            "sur les pages données. Retourne strictement un objet JSON de la forme "
            '{"violations":[{"page":"1","original":"extrait exact",'
            '"proposed":"correction optionnelle","message":"explication"}]}. '
            "Une absence de violation retourne {\"violations\":[]}. "
            "`original` doit être une sous-chaîne exacte du texte de sa page. "
            "Ne signale pas un problème que la règle ne demande pas de vérifier."
        )
        try:
            response = call_chat(
                db,
                system,
                json.dumps(payload, ensure_ascii=False),
                temperature=0.0,
            )
            parsed = _parse_json_object(response)
            entries = parsed.get("violations", []) if isinstance(parsed, dict) else []
            if not isinstance(entries, list):
                raise ValueError("violations must be a list")
        except (AppError, ValueError, TypeError, json.JSONDecodeError):
            failed_call = True
            continue
        except Exception:
            failed_call = True
            continue

        by_page = {target.page: target for target in group}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            page = str(entry.get("page") or "")
            target = by_page.get(page)
            original = entry.get("original")
            if target is None or not isinstance(original, str) or not original.strip():
                continue
            original = original.strip()
            if original not in target.text:
                continue
            proposed = entry.get("proposed")
            proposed = proposed.strip() if isinstance(proposed, str) else ""
            if proposed == original:
                proposed = ""
            message = entry.get("message")
            message = str(message).strip()[:500] if message else rule.topic
            violations.append((target, original, proposed, message))

    if violations:
        target, original, _proposed, _message = violations[0]
        result = RuleResult(
            rule_id=rule.id,
            status="FAIL",
            evidence=_evidence(target, original, rule.semantic_instruction, is_docx, pdf_pages),
        )
        raws = [
            RawSuggestion(
                rule_kind="compiled_checklist" if rule.source == "user_checklist" else "compiled_standard",
                rule_code=rule.id,
                severity=rule.severity,
                message=message,
                original=original,
                proposed=proposed,
                page=target.raw_page,
                span=(0, len(original)),
            )
            for target, original, proposed, message in violations
        ]
        return result, raws
    if failed_call:
        return (
            RuleResult(
                rule_id=rule.id,
                status="INCONCLUSIVE",
                evidence=_evidence(fallback_target, None, rule.semantic_instruction, is_docx, pdf_pages),
            ),
            [],
        )
    return (
        RuleResult(
            rule_id=rule.id,
            status="PASS",
            evidence=_evidence(fallback_target, None, rule.semantic_instruction, is_docx, pdf_pages),
        ),
        [],
    )


def _semantic_groups(targets: list[_TextTarget]) -> list[list[_TextTarget]]:
    groups: list[list[_TextTarget]] = []
    current: list[_TextTarget] = []
    current_len = 0
    total_len = 0
    for target in targets:
        text = target.text.strip()
        if not text or total_len >= _SEMANTIC_TOTAL_CHAR_LIMIT:
            continue
        if len(text) > _SEMANTIC_GROUP_CHAR_LIMIT:
            text = text[:_SEMANTIC_GROUP_CHAR_LIMIT]
            target = replace(target, text=text)
        if current and current_len + len(text) > _SEMANTIC_GROUP_CHAR_LIMIT:
            groups.append(current)
            current = []
            current_len = 0
        current.append(target)
        current_len += len(text)
        total_len += len(text)
    if current:
        groups.append(current)
    return groups


def _parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("semantic response must be an object")
    return parsed


def _manual_suggestions(rule: CompiledRule, targets: list[_TextTarget]) -> list[RawSuggestion]:
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


def _deterministic_suggestions(
    rule: CompiledRule,
    targets: list[_TextTarget],
    result: RuleResult,
    is_docx: bool,
    pdf_pages: list[ParsedPage] | None,
) -> list[RawSuggestion]:
    rule_kind = "compiled_standard" if rule.source == "standard_rule" else "compiled_checklist"
    message = f"Règle compilée non satisfaite: {rule.topic}"
    suggestions: list[RawSuggestion] = []
    for check in rule.checks:
        if check.operator != "regex" or check.expected is None:
            continue
        try:
            matches = [
                (target, match.group(0))
                for target in targets
                for match in re.finditer(str(check.expected), target.text)
                if match.group(0)
            ]
        except re.error:
            matches = []
        for target, original in matches:
            suggestions.append(
                RawSuggestion(
                    rule_kind=rule_kind,
                    rule_code=rule.id,
                    severity=rule.severity,
                    message=message,
                    original=original,
                    proposed="",
                    page=target.raw_page,
                    span=(0, len(original)),
                )
            )
        if suggestions:
            return suggestions

    raw_page = next(
        (target.raw_page for target in targets if target.page == result.evidence.page),
        targets[0].raw_page,
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
            page=raw_page,
            span=(0, len(observed)),
        )
    ]


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