"""Apply reviewed spans to a copy; the source tree remains the stable anchor."""

from __future__ import annotations

from dataclasses import replace

from app.core.ir import IRNode, from_dict, to_dict
from app.core.preliminary_detection import CATEGORIES, is_reviewable
from app.core.preliminary_review import load, require_complete, rules_for
from app.core.procedure_semantics import EXTRA_DESTINATIONS, column_key, heading_scope, table_category, table_heading
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
    requirements: dict[str, list[IRNode]] = {key: [] for key in (*CATEGORIES, *EXTRA_DESTINATIONS)}
    structural = {
        passage["node_id"]: passage["role"]
        for passage in review["passages"]
        if not is_reviewable(passage) and passage["row"] is None
    }
    heading_phases = {
        passage["node_id"]: passage["phase"]
        for passage in review["passages"] if passage.get("role") == "heading" and "phase" in passage
    }
    for passage in review["passages"]:
        if not is_reviewable(passage):
            continue
        grouped.setdefault((passage["node_id"], passage["row"]), []).append(passage)
        if passage["decision"] in requirements:
            original = nodes.get(passage["node_id"])
            content = IRNode(
                id=f"review-{passage['id']}", kind="paragraph", text=passage["text"].strip(),
            )
            if original and passage["row"] is not None:
                row = original.table_rows[passage["row"]]
                header = table_heading({
                    "table_header": original.table_header, "table_rows": original.table_rows,
                }, headings=rules.headings)
                cells = row if passage["text"] == passage["source_text"] else passage["text"].split(" | ")
                if passage["source_text"] == " | ".join(row) and (not header or len(cells) == len(header)):
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
            requirements[passage["decision"]].append(IRNode(
                id=f"review-section-{passage['id']}", kind="section", children=[content],
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
                                else parts[0]["text"].split(" | "))
                elif any(part["decision"] == "body" for part in parts):
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
