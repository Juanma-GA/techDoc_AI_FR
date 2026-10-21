from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.checks.client_bundle import ClientBundle
from app.checks.thales_rules.preparation_toc import map_preparation_pages_to_toc
from app.core.compiled_rule_executor import execute_pdf_rules
from app.core.compiled_rules import CompiledRule
from app.core.page_range import filter_pdf_pages
from app.parsers.pdf_parser import ParsedPdf


def detect_pages_to_modify(
    parsed: ParsedPdf,
    document: Any,
    rules: list[CompiledRule],
    db: Session,
    bundle: ClientBundle,
) -> list[dict[str, Any]]:
    if bundle.page_classifier is not None:
        bundle.page_classifier(parsed, document)
    decisions: list[dict[str, Any]] = []
    for page in parsed.pages:
        applicable = [rule for rule in rules if _rule_targets_page(rule, page.page_type)]
        if not applicable:
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
    map_preparation_pages_to_toc(parsed, decisions)
    return decisions


def _rule_targets_page(rule: CompiledRule, page_type: str | None) -> bool:
    target = rule.target
    if target.page_type is not None and target.page_type != page_type:
        return False
    if target.page_types is not None and page_type not in target.page_types:
        return False
    if target.excluded_page_types and page_type in target.excluded_page_types:
        return False
    return True
