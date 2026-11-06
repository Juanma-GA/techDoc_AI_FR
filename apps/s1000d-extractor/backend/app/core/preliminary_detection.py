"""Local, explainable proposals with lossless anchors into the source IR."""

from __future__ import annotations

from app.core.preliminary_rules import RulesConfig, defaults
from app.core.procedure_semantics import (
    EXTRA_DESTINATIONS,
    REQUIREMENT_CATEGORIES,
    column_key,
    heading_scope,
    is_action,
    normalize,
    passage_role,
    table_anchor_category,
    table_anchor_key,
    table_category,
    table_heading,
)
from app.core.procedure_tags import default_tag_for, tag_options_for

CATEGORIES = REQUIREMENT_CATEGORIES
DESTINATIONS = (*CATEGORIES, *EXTRA_DESTINATIONS, "body", "discard")
RULE_VERSION = 6


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


def _normalized_cell_box(node: dict, row: int, column: int) -> list[float] | None:
    rows = node.get("table_cell_bboxes") or []
    if row >= len(rows) or column >= len(rows[row]):
        return None
    box = rows[row][column]
    width, height = node.get("page_width"), node.get("page_height")
    if not box or not width or not height or width <= 0 or height <= 0:
        return None
    x0, y0, x1, y1 = (float(value) for value in box)
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0 / width, y0 / height, x1 / width, y1 / height]


def _generic_table_marker(text: str, *, headings: dict[str, set[str]]) -> bool:
    label = table_anchor_key(text)
    if (
        not label or ":" in text or len(label) > 64 or len(label.split()) > 6
        or any(character.isdigit() for character in label)
        or label in {"equipment", "object", "removal and installation", "installation and removal"}
    ):
        return False
    phase, _ = heading_scope(text, headings=headings)
    return phase == "unknown"


def _table_anchor_passages(
    node: dict, *, page: int | None, phase: str, rules: RulesConfig,
) -> list[dict] | None:
    rows = node.get("table_rows") or []
    if any(sum(column_key(cell) is not None for cell in row) for row in rows):
        return None
    markers: dict[tuple[int, int], tuple[str, str | None, str | None]] = {}
    for row_index, row in enumerate(rows):
        nonempty_count = sum(bool(cell.strip()) for cell in row)
        may_be_header = nonempty_count >= 2 and row_index + 1 < len(rows)
        for column, cell in enumerate(row):
            text = cell.strip()
            label, separator, inline_value = text.partition(":")
            category = table_anchor_category(label, headings=rules.headings) if separator else None
            if category is not None:
                markers[(row_index, column)] = (label.strip(), category, inline_value.strip() or None)
                continue
            category = table_anchor_category(text, headings=rules.headings)
            if category is not None:
                markers[(row_index, column)] = (text, category, None)
            elif may_be_header and _generic_table_marker(text, headings=rules.headings):
                markers[(row_index, column)] = (text, None, None)

    if not markers:
        return None

    result: list[dict] = []
    for (marker_row, column), (marker, category, inline_value) in markers.items():
        values: list[tuple[int, int, str]] = []
        if inline_value:
            values.append((marker_row, column, inline_value))
        else:
            for value_row in range(marker_row + 1, len(rows)):
                if any(
                    (value_row, marker_column) in markers
                    for marker_column in range(len(rows[value_row]))
                ):
                    break
                if column < len(rows[value_row]) and rows[value_row][column].strip():
                    values.append((value_row, column, rows[value_row][column].strip()))
            if not values:
                nonempty = [
                    (index, cell.strip()) for index, cell in enumerate(rows[marker_row]) if cell.strip()
                ]
                if len(nonempty) == 2 and nonempty[0][0] == column:
                    values.append((marker_row, nonempty[1][0], nonempty[1][1]))

        marker_box = _normalized_cell_box(node, marker_row, column)
        for value_row, value_column, text in values:
            value_box = _normalized_cell_box(node, value_row, value_column)
            anchor_rects = []
            for box in (marker_box, value_box):
                if box is not None and box not in anchor_rects:
                    anchor_rects.append(box)
            suggested = category or "review"
            item = {
                "id": f"{node['id']}:anchor:{marker_row}:{column}:{value_row}:{value_column}",
                "node_id": node["id"],
                "row": value_row,
                "column": value_column,
                "start": 0,
                "end": len(text),
                "source_text": text,
                "text": text,
                "page": page,
                "kind": "paragraph",
                "role": "content",
                "phase": phase,
                "category_hint": category,
                "source_marker": marker,
                "marker_key": table_anchor_key(marker),
                "source_cells": None,
                "source_labels": None,
                "anchor_texts": [marker] if marker == text else [marker, text],
                "anchor_rects": anchor_rects,
                "suggested": suggested,
                "rule": "anchor",
                "decision": None,
                "target_tag": None,
            }
            item["tag_options"] = tag_options_for(item)
            item["target_tag"] = default_tag_for(category, item) if category else None
            result.append(item)
    if not result:
        result.append({
            "id": f"{node['id']}:anchor-layout",
            "node_id": node["id"],
            "row": None,
            "column": None,
            "start": 0,
            "end": 0,
            "source_text": "",
            "text": "",
            "page": page,
            "kind": "table",
            "role": "layout",
            "phase": phase,
            "source_marker": None,
            "marker_key": None,
            "source_cells": None,
            "source_labels": None,
            "anchor_texts": [],
            "anchor_rects": [],
            "suggested": "body",
            "rule": "structure",
            "decision": None,
            "target_tag": None,
            "tag_options": {},
        })
    return result


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
        source_page = (
            (node.get("page") + page_offset if node.get("page") else None)
            if source_format == "pdf" else None
        )
        anchors = (
            _table_anchor_passages(node, page=source_page, phase=phase, rules=active)
            if kind == "table" else None
        )
        if anchors is not None:
            if source_format == "docx":
                total_size = sum(len(item["source_text"]) for item in anchors)
                if page_size and page_size + total_size > 2400:
                    reading_page += 1
                    page_size = 0
                page_size += total_size
                for item in anchors:
                    item["page"] = reading_page
            result.extend(anchors)
            texts: list[tuple[int | None, int | None, str]] = []
        else:
            texts = (
                [
                    (row_index, column, cell.strip())
                    for row_index, cells in enumerate(rows)
                    for column, cell in enumerate(cells)
                    if cell.strip()
                ]
                if kind == "table"
                else [(None, None, node.get("text", ""))]
            )
        for row, column, text in texts:
            if root or not text.strip():
                continue
            if source_format == "docx" and page_size and page_size + len(text) > 2400:
                reading_page += 1
                page_size = 0
            page_size += len(text)
            page = source_page if source_format == "pdf" else reading_page
            role = passage_role(node, row, text, headings=active.headings)
            category, rule = (
                suggestion(text, inherited, phase, node.get("admonition"), rules=active)
                if role == "content" else ("body", "structure")
            )
            source_cells = rows[row] if row is not None else None
            header = table_heading(node, headings=active.headings) if row is not None else []
            cell_title = (
                header[column].strip()
                if header and column is not None and column < len(header) else None
            )
            marker_key = table_anchor_key(cell_title) if cell_title else None
            anchor_rects = []
            anchor_texts = [text]
            if marker_key:
                anchor_texts.insert(0, cell_title)
                if rows and rows[0] == header and column is not None:
                    title_box = _normalized_cell_box(node, 0, column)
                    if title_box is not None:
                        anchor_rects.append(title_box)
            value_box = (
                _normalized_cell_box(node, row, column)
                if row is not None and column is not None else None
            )
            if value_box is not None and value_box not in anchor_rects:
                anchor_rects.append(value_box)
            passage = {
                "id": (
                    f"{node['id']}:{row}:{column}:0"
                    if row is not None else f"{node['id']}:text:0"
                ),
                "node_id": node["id"],
                "row": row,
                "column": column,
                "start": 0,
                "end": len(text),
                "source_text": text,
                "text": text,
                "source_marker": None,
                "marker_key": marker_key,
                "source_cells": source_cells,
                "source_labels": header if row is not None and len(header) == len(rows[row]) else None,
                "anchor_texts": anchor_texts,
                "anchor_rects": anchor_rects,
                "page": page,
                "kind": kind,
                "role": role,
                "phase": phase,
                "category_hint": inherited,
                "admonition": node.get("admonition"),
                "suggested": category,
                "rule": rule,
                "decision": None,
                "target_tag": None,
            }
            passage["tag_options"] = tag_options_for(passage)
            passage["target_tag"] = (
                default_tag_for(category, passage) if category != "review" else None
            )
            result.append(passage)
        for child in node.get("children", []):
            visit(child, inherited, phase)

    visit(tree, root=True)
    return result
