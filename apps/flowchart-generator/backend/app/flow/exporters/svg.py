"""Export SVG autonome (apercu + fichier). Couleurs issues des tokens (theme light)."""

from __future__ import annotations

from xml.sax.saxutils import escape

from app.flow.layout import Box, compute_layout
from app.flow.model import FlowGraph, NodeType, base_shape
from app.flow.routing import extent, route_edges, wrap
from app.flow.theme import css, tint

FONT = "Inter, Segoe UI, Arial, sans-serif"


def _rgb(c: tuple[int, int, int]) -> str:
    return f"rgb({c[0]},{c[1]},{c[2]})"


def _shape(node_type: NodeType, b: Box, fill: str, stroke: str) -> str:
    attrs = f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"'
    x, y, w, h = b.x, b.y, b.w, b.h
    if node_type in (NodeType.start, NodeType.end):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" {attrs}/>'
    if node_type == NodeType.decision:
        pts = f"{b.cx},{y} {x + w},{b.cy} {b.cx},{y + h} {x},{b.cy}"
        return f'<polygon points="{pts}" {attrs}/>'
    if node_type == NodeType.io:
        k = 16
        pts = f"{x + k},{y} {x + w},{y} {x + w - k},{y + h} {x},{y + h}"
        return f'<polygon points="{pts}" {attrs}/>'
    if node_type == NodeType.document:
        d = (
            f"M{x},{y} H{x + w} V{y + h - 8} "
            f"C{x + w * 0.75},{y + h - 22} {x + w * 0.25},{y + h + 8} {x},{y + h - 8} Z"
        )
        return f'<path d="{d}" {attrs}/>'
    if node_type == NodeType.subprocess:
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" {attrs}/>'
            f'<line x1="{x + 10}" y1="{y}" x2="{x + 10}" y2="{y + h}" '
            f'stroke="{stroke}" stroke-width="1.2"/>'
            f'<line x1="{x + w - 10}" y1="{y}" x2="{x + w - 10}" y2="{y + h}" '
            f'stroke="{stroke}" stroke-width="1.2"/>'
        )
    if node_type == NodeType.connector:
        r = min(w, h) / 2
        return f'<circle cx="{b.cx}" cy="{b.cy}" r="{r}" {attrs}/>'
    if node_type == NodeType.safety:
        k = min(18.0, w / 6)
        pts = f"{x + k},{y} {x + w - k},{y} {x + w},{b.cy} {x + w - k},{y + h} {x + k},{y + h} {x},{b.cy}"
        return f'<polygon points="{pts}" {attrs}/>'
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" {attrs}/>'


def _text(lines: list[str], cx: float, cy: float, color: str, size: int = 12) -> str:
    top = cy - (len(lines) - 1) * (size + 2) / 2
    spans = "".join(
        f'<tspan x="{cx}" y="{top + i * (size + 2)}">{escape(line)}</tspan>' for i, line in enumerate(lines)
    )
    return (
        f'<text font-family="{FONT}" font-size="{size}" fill="{color}" text-anchor="middle" '
        f'dominant-baseline="middle">{spans}</text>'
    )


def render_svg(graph: FlowGraph) -> str:
    layout = compute_layout(graph)
    routed = route_edges(graph, layout)
    width, height = extent(layout, routed)
    line, text, dim = css("line"), css("text"), css("dim")
    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
        f'aria-label="{escape(graph.title, {chr(34): "&quot;"})}">',
        f"<title>{escape(graph.title)}</title>",
        "<defs>"
        f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{line}"/></marker></defs>',
        f'<rect width="100%" height="100%" fill="{css("bg")}"/>',
    ]
    for _, label, band in layout.lanes:
        out.append(
            f'<rect x="{band.x}" y="{band.y}" width="{band.w}" height="{band.h}" '
            f'fill="{css("panel")}" stroke="{dim}" stroke-width="0.8" stroke-dasharray="4 3"/>'
        )
        if layout.direction == "TB":
            out.append(_text(wrap(label, 26, 1), band.cx, band.y + 17, text, 13))
        else:
            out.append(
                f'<text font-family="{FONT}" font-size="13" fill="{text}" text-anchor="middle" '
                f'transform="translate({band.x + 17},{band.cy}) rotate(-90)">{escape(label[:40])}</text>'
            )
    for r in routed:
        pts = " ".join(f"{x},{y}" for x, y in r.points)
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="{line}" stroke-width="1.4" '
            'marker-end="url(#arrow)"/>'
        )
        if r.edge.label:
            lx, ly = r.label_at
            w = 8 + 6.5 * min(len(r.edge.label), 24)
            out.append(
                f'<rect x="{lx - w / 2}" y="{ly - 9}" width="{w}" height="18" rx="3" fill="{css("bg")}"/>'
            )
            out.append(_text([r.edge.label[:24]], lx, ly, dim, 11))
    for n in graph.nodes:
        b = layout.boxes[n.id]
        key = n.type.value
        shape = base_shape(n.type)
        details = n.details()
        tip = "\n".join(f"{k}: {v}" for k, v in details.items())
        out.append(f"<g><title>{escape(n.label + (chr(10) + tip if tip else ''))}</title>")
        out.append(_shape(shape, b, _rgb(tint(key, 0.82)), css(key)))
        width_chars = 16 if shape == NodeType.decision else 22
        out.append(_text(wrap(n.label, width_chars, 3), b.cx, b.cy, text))
        if n.ref:
            out.append(
                f'<text font-family="JetBrains Mono, Consolas, monospace" font-size="9" fill="{dim}" '
                f'x="{b.x}" y="{b.y - 4}">{escape(n.ref[:40])}</text>'
            )
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)
