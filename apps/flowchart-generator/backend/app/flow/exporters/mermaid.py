"""Export Mermaid (flowchart) : sous-graphes par couloir, formes ISO 5807 approchees."""

from __future__ import annotations

from app.flow.model import FlowGraph, NodeType
from app.flow.theme import css, tint_hex

_SHAPES: dict[NodeType, tuple[str, str]] = {
    NodeType.start: ("([", "])"),
    NodeType.end: ("([", "])"),
    NodeType.process: ("[", "]"),
    NodeType.decision: ("{", "}"),
    NodeType.io: ("[/", "/]"),
    NodeType.document: (">", "]"),
    NodeType.subprocess: ("[[", "]]"),
    NodeType.connector: ("((", "))"),
    NodeType.check: ("{", "}"),
    NodeType.repair: ("[", "]"),
    NodeType.safety: ("{{", "}}"),
}


_RESERVED = {"end", "subgraph", "graph", "flowchart", "class", "classdef", "style", "click", "direction"}


def _mid(node_id: str) -> str:
    """Mermaid refuse certains mots-cles comme identifiants (ex. `end`)."""
    return f"n_{node_id}" if node_id.lower() in _RESERVED else node_id.replace(".", "_")


def _q(text: str) -> str:
    return '"' + text.replace('"', "#quot;").replace("\n", " ") + '"'


def _node(n_id: str, label: str, node_type: NodeType) -> str:
    left, right = _SHAPES[node_type]
    return f"{_mid(n_id)}{left}{_q(label)}{right}:::t_{node_type.value}"


def render_mermaid(graph: FlowGraph) -> str:
    out = ["---", f"title: {graph.title}", "---", f"flowchart {'TD' if graph.direction == 'TB' else 'LR'}"]
    by_lane: dict[str | None, list[str]] = {}
    for n in graph.nodes:
        by_lane.setdefault(n.lane, []).append(_node(n.id, n.label, n.type))
    for line in by_lane.pop(None, []):
        out.append(f"    {line}")
    for lane in graph.lanes:
        out.append(f"    subgraph {_mid('lane_' + lane.id)}[{_q(lane.label)}]")
        out.extend(f"        {line}" for line in by_lane.get(lane.id, []))
        out.append("    end")
    for e in graph.edges:
        label = e.label.replace("|", "/").replace('"', "'")
        arrow = f"-->|{_q(label)}|" if label else "-->"
        out.append(f"    {_mid(e.source)} {arrow} {_mid(e.target)}")
    for t in NodeType:
        out.append(
            f"    classDef t_{t.value} fill:#{tint_hex(t.value, 0.82)},"
            f"stroke:{css(t.value)},color:{css('text')}"
        )
    return "\n".join(out) + "\n"
