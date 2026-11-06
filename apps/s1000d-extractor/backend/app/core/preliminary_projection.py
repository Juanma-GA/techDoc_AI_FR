"""Apply reviewed spans to a copy; the source tree remains the stable anchor."""

from __future__ import annotations

from dataclasses import replace

from app.core.ir import Candidate, IRNode, from_dict, to_dict
from app.core.preliminary_detection import CATEGORIES, is_reviewable
from app.core.preliminary_review import load, require_complete, rules_for
from app.core.procedure_semantics import (
    EXTRA_DESTINATIONS,
    column_key,
    heading_scope,
    table_category,
    table_heading,
)
from app.db.models import Document


def sync_mappings(source: IRNode, rendered: IRNode) -> None:
    mapped = {node.id: node for node in rendered.walk()}
    for node in source.walk():
        if node.id in mapped:
            node.candidates = mapped[node.id].candidates
            node.confidence = mapped[node.id].confidence


def reviewed_root(doc: Document, dm: dict, root: IRNode) -> IRNode:
    if dm["dm_type"] != "procedural":
        return root
    require_complete(doc, dm["dm_id"])
    review = load(doc)["reviews"][dm["dm_id"]]
    if review["status"] == "skipped":
        return from_dict(to_dict(root))
    rules = rules_for(doc)
    copy = from_dict(to_dict(root))
    nodes = {node.id: node for node in copy.walk()}
    grouped: dict[tuple[str, int | None], list[dict]] = {}
    anchored_nodes: set[str] = set()
    body_anchors: dict[str, list[IRNode]] = {}
    requirements: dict[str, list[IRNode]] = {key: [] for key in (*CATEGORIES, *EXTRA_DESTINATIONS)}
    resource_cells: dict[tuple[str, int, str], list[dict]] = {}
    passages = [
        {**passage, "decision": "body"}
        if review.get("partial") and is_reviewable(passage) and passage["decision"] is None
        else passage
        for passage in review["passages"]
    ]
    structural = {
        passage["node_id"]: passage["role"]
        for passage in passages
        if not is_reviewable(passage) and passage["row"] is None
    }
    heading_phases = {
        passage["node_id"]: passage["phase"]
        for passage in passages if passage.get("role") == "heading" and "phase" in passage
    }
    for passage in passages:
        if not is_reviewable(passage):
            continue
        if passage.get("source_marker"):
            anchored_nodes.add(passage["node_id"])
            content = IRNode(
                id=f"review-{passage['id']}", kind="paragraph", text=passage["text"].strip(),
            )
            target_tag = passage.get("target_tag")
            if target_tag:
                content.candidates = [Candidate(target_tag, 1.0, "human-reviewed")]
            if passage["decision"] in requirements:
                requirements[passage["decision"]].append(IRNode(
                    id=f"review-section-{passage['id']}", kind="section", children=[content],
                ))
            elif passage["decision"] == "body":
                body_anchors.setdefault(passage["node_id"], []).append(content)
            continue
        grouped.setdefault((passage["node_id"], passage["row"]), []).append(passage)
        if passage["decision"] in requirements:
            original = nodes.get(passage["node_id"])
            if (
                original
                and original.kind == "table"
                and passage["row"] is not None
                and passage["decision"] in {"personnel", "support", "supplies", "spares"}
            ):
                resource_cells.setdefault(
                    (passage["node_id"], passage["row"], passage["decision"]), [],
                ).append(passage)
                continue
            content = IRNode(
                id=f"review-{passage['id']}", kind="paragraph", text=passage["text"].strip(),
            )
            if original and passage["row"] is not None:
                row = original.table_rows[passage["row"]]
                header = table_heading({
                    "table_header": original.table_header, "table_rows": original.table_rows,
                }, headings=rules.headings)
                cells = row if passage["text"] == passage["source_text"] else [passage["text"]]
                if (
                    passage["text"] == passage["source_text"]
                    and passage["start"] == 0
                    and passage.get("source_cells") == row
                    and passage["source_text"] == " ".join(
                        cell.strip() for cell in row if cell.strip()
                    )
                    and (not header or len(cells) == len(header))
                ):
                    content = IRNode(
                        id=content.id, kind="table", table_rows=[cells],
                        table_header=[
                            "name" if column_key(cell) is None and table_category([cell], headings=rules.headings)
                            else cell for cell in header
                        ],
                    )
            if original and original.kind == "admonition" and passage["decision"] in {"safety", "common"}:
                content.kind = "admonition"
                content.admonition = original.admonition or "warning"
            target_tag = passage.get("target_tag")
            if target_tag:
                content.candidates = [Candidate(target_tag, 1.0, "human-reviewed")]
            requirements[passage["decision"]].append(IRNode(
                id=f"review-section-{passage['id']}", kind="section", children=[content],
            ))

    for (node_id, row_index, destination), parts in resource_cells.items():
        original = nodes[node_id]
        source_row = original.table_rows[row_index]
        row = [""] * len(source_row)
        tags: list[str | None] = [None] * len(source_row)
        grouped_columns: dict[int, list[dict]] = {}
        for part in parts:
            column = part.get("column")
            if isinstance(column, int) and 0 <= column < len(source_row):
                grouped_columns.setdefault(column, []).append(part)
        for column, column_parts in grouped_columns.items():
            row[column] = "".join(
                part["text"] for part in sorted(column_parts, key=lambda item: item["start"])
            ).strip()
            tags[column] = column_parts[-1].get("target_tag")
        header = table_heading(
            {"table_header": original.table_header, "table_rows": original.table_rows},
            headings=rules.headings,
        )
        content = IRNode(
            id=f"review-resource-{node_id}-{row_index}-{destination}",
            kind="table",
            table_rows=[row],
            table_header=header or None,
            reviewed_table_cell_tags=[tags],
        )
        requirements[destination].append(IRNode(
            id=f"review-section-resource-{node_id}-{row_index}-{destination}",
            kind="section",
            children=[content],
        ))

    def body(parts: list[dict]) -> str:
        return "".join(
            part["text"] for part in sorted(parts, key=lambda p: p["start"])
            if part["decision"] == "body"
        )

    def prune(node: IRNode, *, is_root: bool = False) -> list[IRNode]:
        had_children = bool(node.children)
        node.children = [item for child in node.children for item in prune(child)]
        if structural.get(node.id) in {"marker", "layout"}:
            return []
        if node.id in anchored_nodes:
            return body_anchors.get(node.id, [])
        if node.table_rows:
            header = table_heading(
                {"table_header": node.table_header, "table_rows": node.table_rows}, headings=rules.headings,
            )
            rows = []
            for index, row in enumerate(node.table_rows):
                if index == 0 and row == header:
                    continue
                parts = grouped.get((node.id, index))
                if not parts:
                    rows.append(row)
                elif all(part["decision"] == "body" for part in parts) and len(parts) == 1:
                    rows.append(row if parts[0]["text"] == parts[0]["source_text"]
                                else [parts[0]["text"]])
                elif any(part["decision"] == "body" for part in parts):
                    if all(part.get("column") is not None for part in parts):
                        projected_row = list(row)
                        for part in parts:
                            column = part["column"]
                            projected_row[column] = (
                                part["text"] if part["decision"] == "body" else ""
                            )
                        if any(cell.strip() for cell in projected_row):
                            rows.append(projected_row)
                    else:
                        rows.append([body(parts)])
            node.table_rows = rows
            node.table_header = header or None
            if not rows:
                return node.children
        parts = grouped.get((node.id, None))
        if parts:
            text = body(parts)
            if text != node.text:
                node.text = text
                node.inline_runs = []
                node.refs = None
            if not text.strip() and node.kind != "figure":
                return node.children
        if not is_root and node.kind == "section":
            phase = heading_phases.get(node.id, heading_scope(node.text)[0])
            if phase in {"preliminary", "closing", "common"} or (had_children and not node.children):
                return node.children
        if not is_root and not node.text.strip() and not node.children and node.kind not in {"table", "figure"}:
            return []
        return [node]

    prune(copy, is_root=True)
    return replace(copy, reviewed_requirements=requirements)
