"""Local, explainable proposals with lossless anchors into the source IR."""

from __future__ import annotations

from app.core.preliminary_rules import RulesConfig, defaults
from app.core.procedure_semantics import (
    EXTRA_DESTINATIONS,
    REQUIREMENT_CATEGORIES,
    heading_scope,
    is_action,
    normalize,
    passage_role,
    table_category,
    table_heading,
)

CATEGORIES = REQUIREMENT_CATEGORIES
DESTINATIONS = (*CATEGORIES, *EXTRA_DESTINATIONS, "body", "discard")
RULE_VERSION = 3


def is_reviewable(passage: dict) -> bool:
    return passage.get("role", "content") == "content"


def suggestion(
    text: str, inherited: str | None, phase: str = "unknown", admonition: str | None = None,
    *, rules: RulesConfig | None = None,
) -> tuple[str, str]:
    if admonition in {"warning", "caution"} and phase in {"closing", "common"}:
        return "review", "multiple"
    if phase in {"main", "closing", "common"}:
        return {"main": "body", "closing": "closing", "common": "common"}[phase], phase
    if admonition in {"warning", "caution"}:
        return "safety", "admonition"
    if inherited:
        return inherited, "heading"
    if is_action(text):
        return "body", "action"
    active = rules if rules is not None else defaults()
    matches = [category for category, rule in active.keywords.items() if rule.search(normalize(text))]
    if len(matches) > 1:
        return "review", "multiple"
    if matches:
        return matches[0], "keywords"
    return "body", "unmatched"


def passages(
    tree: dict, *, source_format: str, page_offset: int, rules: RulesConfig | None = None,
) -> list[dict]:
    result: list[dict] = []
    reading_page, page_size = 1, 0
    active = rules if rules is not None else defaults()

    def visit(node: dict, inherited: str | None = None, phase: str = "unknown", *, root: bool = False) -> None:
        nonlocal reading_page, page_size
        kind = node["kind"]
        if kind in {"section", "title"}:
            scoped_phase, category = heading_scope(node.get("text", ""), headings=active.headings)
            if scoped_phase != "unknown":
                phase, inherited = scoped_phase, category
        if kind == "table" and not inherited and phase not in {"main", "closing", "common"}:
            inherited = table_category(table_heading(node, headings=active.headings), headings=active.headings)
        rows = node.get("table_rows") or []
        texts = (
            [(index, " | ".join(row)) for index, row in enumerate(rows)]
            if kind == "table" else [(None, node.get("text", ""))]
        )
        for row, text in texts:
            if root or not text.strip():
                continue
            if source_format == "docx" and page_size and page_size + len(text) > 2400:
                reading_page += 1
                page_size = 0
            page_size += len(text)
            page = (
                (node.get("page") + page_offset if node.get("page") else None)
                if source_format == "pdf" else reading_page
            )
            role = passage_role(node, row, text, headings=active.headings)
            category, rule = (
                suggestion(text, inherited, phase, node.get("admonition"), rules=active)
                if role == "content" else ("body", "structure")
            )
            result.append({
                "id": f"{node['id']}:{row if row is not None else 'text'}:0",
                "node_id": node["id"],
                "row": row,
                "start": 0,
                "end": len(text),
                "source_text": text,
                "text": text,
                "page": page,
                "kind": kind,
                "role": role,
                "phase": phase,
                "category_hint": inherited,
                "admonition": node.get("admonition"),
                "suggested": category,
                "rule": rule,
                "decision": None,
            })
        for child in node.get("children", []):
            visit(child, inherited, phase)

    visit(tree, root=True)
    return result
