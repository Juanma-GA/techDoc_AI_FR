"""Public facade for compiled-rule execution."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.checks.raw import RawSuggestion
from app.core.compiled_rules import CompiledRule, RuleResult
from app.core.llm_suggester import call_chat
from app.core.logging import get_logger
from app.parsers.docx_parser import Block
from app.parsers.pdf_parser import ParsedPage, ParsedPdf
from app.core.compiled_rule_runtime import (
    _EvalContext,
    _TextTarget,
    scope_targets as _scope_targets,
    evidence as _evidence,
    document_metadata as _document_metadata,
    page_span_ranges,
)

_LOG_TEXT_LIMIT = 800
_logger = get_logger(__name__)


def execute_pdf_rules(
    parsed: ParsedPdf,
    rules: list[CompiledRule],
    db: Session | None = None,
    document: Any | None = None,
) -> tuple[list[RuleResult], list[RawSuggestion]]:
    targets = [
        _TextTarget(
            page=str(page.page),
            text=page.text,
            raw_page=page.page,
            page_type=page.page_type,
            page_modified=page.is_modified,
            span_ranges=page_span_ranges(page),
        )
        for page in parsed.pages
    ]
    return _execute(
        rules,
        targets,
        parsed.pages,
        is_docx=False,
        db=db,
        document=document,
        parsed_pdf=parsed,
    )


def execute_docx_rules(
    blocks: list[Block],
    rules: list[CompiledRule],
    db: Session | None = None,
    document: Any | None = None,
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
    return _execute(rules, targets, None, is_docx=True, blocks=blocks, db=db, document=document)


def _execute(
    rules: list[CompiledRule],
    targets: list[_TextTarget],
    pdf_pages: list[ParsedPage] | None,
    *,
    is_docx: bool,
    blocks: list[Block] | None = None,
    db: Session | None = None,
    document: Any | None = None,
    parsed_pdf: ParsedPdf | None = None,
) -> tuple[list[RuleResult], list[RawSuggestion]]:
    from app.core.compiled_rule_operators import condition_met, evaluate_rule

    results: list[RuleResult] = []
    raws: list[RawSuggestion] = []
    ctx = _EvalContext(
        all_targets=targets,
        is_docx=is_docx,
        blocks=blocks,
        pdf_pages=pdf_pages,
        document=document,
        db=db,
        parsed_pdf=parsed_pdf,
    )
    metadata = _document_metadata(document)
    _logger.info(
        "compiled_rules_execution_started",
        rule_count=len(rules),
        target_count=len(targets),
        pages=[target.page for target in targets],
        document_metadata=metadata,
        is_docx=is_docx,
    )
    for rule in rules:
        _logger.info(
            "compiled_rule_started",
            rule_id=rule.id,
            topic=rule.topic,
            execution=rule.execution,
            target=rule.target.model_dump(mode="json"),
            checks=[check.model_dump(mode="json") for check in rule.checks],
            document_metadata=metadata,
        )
        if rule.only_if is not None and not condition_met(rule.only_if, ctx):
            _logger.info(
                "compiled_rule_skipped",
                rule_id=rule.id,
                reason="only_if_not_met",
                condition=rule.only_if.model_dump(mode="json"),
                document_metadata=metadata,
            )
            continue
        scoped = _scope_targets(
            rule.target,
            targets,
            is_docx=is_docx,
            blocks=blocks,
            pdf_pages=pdf_pages,
        )
        _logger.info(
            "compiled_rule_scoped",
            rule_id=rule.id,
            target=rule.target.model_dump(mode="json"),
            target_count=len(scoped or []),
            targets=[_target_log_payload(target) for target in scoped or []],
        )
        if rule.execution == "semantic":
            from app.core.compiled_rule_semantic import execute_semantic

            result, semantic_raws = execute_semantic(
                rule, scoped or [], db, is_docx, pdf_pages, document
            )
            results.append(result)
            raws.extend(semantic_raws)
            _log_rule_finished(rule.id, result, len(semantic_raws))
            continue
        if rule.execution == "manual":
            from app.core.compiled_rule_suggestions import manual_suggestions

            result = RuleResult(rule_id=rule.id, status="MANUAL")
            manual_raws = manual_suggestions(rule, scoped or targets)
            results.append(result)
            raws.extend(manual_raws)
            _log_rule_finished(rule.id, result, len(manual_raws))
            continue
        if rule.execution == "unsupported":
            result = RuleResult(rule_id=rule.id, status="UNSUPPORTED")
            results.append(result)
            _log_rule_finished(rule.id, result, 0)
            continue
        if scoped is None or not scoped:
            if (
                rule.target.page_type is not None
                or rule.target.page_types is not None
                or rule.target.excluded_page_types is not None
            ):
                _logger.info(
                    "compiled_rule_skipped",
                    rule_id=rule.id,
                    reason="target_page_type_not_found",
                    page_type=rule.target.page_type,
                    page_types=rule.target.page_types,
                    excluded_page_types=rule.target.excluded_page_types,
                )
                continue
            result = RuleResult(
                rule_id=rule.id,
                status="INCONCLUSIVE",
                evidence=_evidence(targets[0] if targets else None, None, None, is_docx, pdf_pages),
            )
            results.append(result)
            _log_rule_finished(rule.id, result, 0)
            continue
        result = evaluate_rule(rule, scoped, is_docx, pdf_pages, ctx)
        results.append(result)
        rule_raws: list[RawSuggestion] = []
        if result.status == "FAIL" and result.evidence is not None:
            from app.core.compiled_rule_suggestions import deterministic_suggestions

            rule_raws = deterministic_suggestions(rule, scoped, result, pdf_pages, ctx)
            raws.extend(rule_raws)
        _log_rule_finished(rule.id, result, len(rule_raws))
    return results, raws


def _short_text(value: str, limit: int = _LOG_TEXT_LIMIT) -> str:
    value = value.replace("\n", " ").strip()
    return value if len(value) <= limit else f"{value[:limit - 1]}..."


def _target_log_payload(target: _TextTarget) -> dict[str, object]:
    return {
        "page": target.page,
        "raw_page": target.raw_page,
        "target_id": target.target_id,
        "text": _short_text(target.text),
        "page_type": target.page_type,
    }


def _log_rule_finished(rule_id: str, result: RuleResult, raw_count: int) -> None:
    _logger.info(
        "compiled_rule_finished",
        rule_id=rule_id,
        status=result.status,
        evidence_page=result.evidence.page if result.evidence else None,
        observed=_short_text(result.evidence.observed_value or "") if result.evidence else None,
        expected=_short_text(result.evidence.expected_value or "") if result.evidence else None,
        suggestion_count=raw_count,
    )
