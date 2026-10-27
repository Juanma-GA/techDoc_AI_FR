"""Apply reviewed spans to a copy; the source tree remains the stable anchor."""

from __future__ import annotations

from dataclasses import replace

from app.core.ir import IRNode, from_dict, to_dict
from app.core.preliminary_detection import CATEGORIES
from app.core.preliminary_review import load, require_complete
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
    copy = from_dict(to_dict(root))
    nodes = {node.id: node for node in copy.walk()}
    grouped: dict[tuple[str, int | None], list[dict]] = {}
    requirements: dict[str, list[IRNode]] = {key: [] for key in CATEGORIES}
    for passage in review["passages"]:
        grouped.setdefault((passage["node_id"], passage["row"]), []).append(passage)
        if passage["decision"] in CATEGORIES:
            original = nodes.get(passage["node_id"])
            content = IRNode(
                id=f"review-{passage['id']}", kind="paragraph", text=passage["text"].strip(),
            )
            if original and original.kind == "admonition" and passage["decision"] == "safety":
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
        node.children = [item for child in node.children for item in prune(child)]
        if node.table_rows:
            rows = []
            for index, row in enumerate(node.table_rows):
                parts = grouped.get((node.id, index))
                if not parts:
                    rows.append(row)
                elif all(part["decision"] == "body" for part in parts) and len(parts) == 1:
                    rows.append(row if parts[0]["text"] == parts[0]["source_text"]
                                else parts[0]["text"].split(" | "))
                elif any(part["decision"] == "body" for part in parts):
                    rows.append([body(parts)])
            node.table_rows = rows
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
        if not is_root and not node.text.strip() and not node.children and node.kind not in {"table", "figure"}:
            return []
        return [node]

    prune(copy, is_root=True)
    return replace(copy, reviewed_requirements=requirements)
