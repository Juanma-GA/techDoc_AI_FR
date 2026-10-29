from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.checks.client_bundle import ClientBundle
from app.checks.thales_rules.page_classifier import page_classification_evidence
from app.checks.thales_rules.preparation_toc import map_preparation_pages_to_toc
from app.checks.thales_rules.section_detection import classify_preparation_sections
from app.core.compiled_rule_executor import execute_pdf_rules
from app.core.compiled_rules import CompiledRule
from app.core.logging import get_logger
from app.core.page_range import filter_pdf_pages
from app.parsers.pdf_parser import ParsedPdf

_logger = get_logger(__name__)

# Rules whose verdict depends on which other pages were found to be modified.
DECISION_DEPENDENT_RULES = frozenset({"CUSTOM_PREP_LEP_MODIFIED_PAGES"})


def _mark_commented_pages(parsed: ParsedPdf, decisions: list[dict[str, Any]]) -> None:
    """Expose the pages decided so far as modified (commented) to the document rules."""
    modified = {item["page"]: item["is_modified"] for item in decisions}
    for page in parsed.pages:
        page.is_modified = modified.get(page.page)


def detect_pages_to_modify(
    parsed: ParsedPdf,
    document: Any,
    rules: list[CompiledRule],
    db: Session,
    bundle: ClientBundle,
    classification_overrides: dict[str, dict[str, str | None]] | None = None,
    metadata: Mapping[str, Any] | None = None,
    page_titles: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    if bundle.page_classifier is not None:
        bundle.page_classifier(parsed, document)
    overrides = classification_overrides or {}
    analysis = classify_preparation_sections(parsed, metadata or {}, page_titles, overrides)
    classification = _apply_classification_overrides(
        parsed, overrides, analysis
    )
    decisions: list[dict[str, Any]] = []
    pages_without_rules: list[dict[str, int | str | None]] = []
    deferred_pages = {
        page.page
        for page in parsed.pages
        if any(
            rule.id in DECISION_DEPENDENT_RULES and _rule_targets_page(rule, page.page_type)
            for rule in rules
        )
    }
    ordered_pages = sorted(parsed.pages, key=lambda item: item.page in deferred_pages)
    commented_pages_marked = False
    for page in ordered_pages:
        if page.page in deferred_pages and not commented_pages_marked:
            _mark_commented_pages(parsed, decisions)
            commented_pages_marked = True
        applicable = [rule for rule in rules if _rule_targets_page(rule, page.page_type)]
        if not applicable:
            pages_without_rules.append(
                {"page": page.page, "page_type": page.page_type}
            )
            decisions.append(
                {
                    "page": page.page,
                    "page_type": page.page_type,
                    "is_modified": None,
                    "decision_status": "no_applicable_rule",
                    "rule_results": [],
                    "failures": [],
                    "review_reasons": [],
                }
            )
            continue

        scoped = filter_pdf_pages(parsed, [page.page])
        results, _suggestions = execute_pdf_rules(
            scoped,
            applicable,
            db=db,
            document=document,
            client_operations=bundle.operations,
            client_entities=bundle.mapping.entities,
        )
        rules_by_id = {rule.id: rule for rule in applicable}
        rule_results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        review_reasons: list[dict[str, Any]] = []
        for result in results:
            rule = rules_by_id.get(result.rule_id)
            status = result.status
            if (
                not page.has_text_layer
                and rule is not None
                and rule.checks
                and all(check.operator == "font_size_equals" for check in rule.checks)
                and status in {"PASS", "FAIL"}
            ):
                status = "INCONCLUSIVE"
            message = (
                rule.failure_message or rule.source_instruction or rule.topic
                if rule is not None
                else status
            )
            reason = {
                "rule_id": result.rule_id,
                "title": rule.topic if rule is not None else result.rule_id,
                "message": message,
                "status": status,
            }
            rule_results.append(
                {
                    "rule_id": result.rule_id,
                    "title": reason["title"],
                    "message": message,
                    "status": status,
                }
            )
            if status == "FAIL":
                failures.append(reason)
            elif status in {"MANUAL", "INCONCLUSIVE", "UNSUPPORTED"}:
                review_reasons.append(reason)

        is_modified = True if failures else False if results and not review_reasons else None
        if is_modified is True:
            status = "selected"
        elif is_modified is False:
            status = "not_selected"
        else:
            status = "needs_review"
        decisions.append(
            {
                "page": page.page,
                "page_type": page.page_type,
                "is_modified": is_modified,
                "decision_status": status,
                "rule_results": rule_results,
                "failures": failures,
                "review_reasons": review_reasons,
            }
        )
    decisions.sort(key=lambda item: item["page"])
    map_preparation_pages_to_toc(parsed, decisions)
    for decision in decisions:
        decision.update(classification[decision["page"]])
    _logger.info(
        "preparation_page_rules_resolved",
        page_count=len(parsed.pages),
        page_type_counts=dict(
            Counter(page.page_type or "unclassified" for page in parsed.pages)
        ),
        rule_target_page_types=sorted(
            {
                page_type
                for rule in rules
                for page_type in (
                    rule.target.page_type,
                    *(rule.target.page_types or ()),
                )
                if page_type is not None
            }
        ),
        no_applicable_rule_count=len(pages_without_rules),
        no_applicable_rule_pages=pages_without_rules[:20],
    )
    return decisions


def _apply_classification_overrides(
    parsed: ParsedPdf,
    overrides: dict[str, dict[str, str | None]],
    analysis: dict[int, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Apply manual page types and describe how each page was classified."""
    classification: dict[int, dict[str, Any]] = {}
    for page in parsed.pages:
        detected_type = page.page_type
        evidence = page_classification_evidence(page)
        override = overrides.get(str(page.page)) or {}
        manual_type = override.get("page_type")
        manual_document_page = override.get("document_page")
        if manual_type is not None:
            page.page_type = manual_type
            source = "manual"
        elif detected_type is not None:
            source = "auto"
        else:
            source = "unclassified"
        details = dict(analysis[page.page])
        if source == "manual":
            details["classification_status"] = "manual"
        manual_title = override.get("page_title")
        if manual_title is not None:
            details["page_title"] = manual_title
        classification[page.page] = {
            "page_type_source": source,
            "detected_page_type": detected_type,
            "document_page": manual_document_page or evidence["footer_page_key"],
            "document_page_source": "manual" if manual_document_page else "auto",
            "classification_evidence": evidence,
            **details,
        }
    return classification


def _rule_targets_page(rule: CompiledRule, page_type: str | None) -> bool:
    target = rule.target
    if target.page_type is not None and target.page_type != page_type:
        return False
    if target.page_types is not None and page_type not in target.page_types:
        return False
    if target.excluded_page_types and page_type in target.excluded_page_types:
        return False
    return True
