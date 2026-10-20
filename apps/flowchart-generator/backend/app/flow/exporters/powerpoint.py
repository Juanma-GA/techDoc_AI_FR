"""Export PowerPoint (.pptx) : formes flowchart natives + connecteurs coudes colles aux formes.

Les connecteurs restent attaches lorsque l'utilisateur deplace les formes dans PowerPoint.
"""

from __future__ import annotations

import io

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from app.flow.layout import compute_layout
from app.flow.model import FlowGraph, NodeType
from app.flow.routing import extent, route_edges
from app.flow.theme import hex6, tint_hex

PX = 9525
MAX_SLIDE_EMU = 56 * 914400
TITLE_PX = 50

_SHAPES: dict[NodeType, MSO_SHAPE] = {
    NodeType.start: MSO_SHAPE.FLOWCHART_TERMINATOR,
    NodeType.end: MSO_SHAPE.FLOWCHART_TERMINATOR,
    NodeType.process: MSO_SHAPE.FLOWCHART_PROCESS,
    NodeType.decision: MSO_SHAPE.FLOWCHART_DECISION,
    NodeType.io: MSO_SHAPE.FLOWCHART_DATA,
    NodeType.document: MSO_SHAPE.FLOWCHART_DOCUMENT,
    NodeType.subprocess: MSO_SHAPE.FLOWCHART_PREDEFINED_PROCESS,
    NodeType.connector: MSO_SHAPE.FLOWCHART_CONNECTOR,
    NodeType.check: MSO_SHAPE.FLOWCHART_DECISION,
    NodeType.repair: MSO_SHAPE.FLOWCHART_PROCESS,
    NodeType.safety: MSO_SHAPE.FLOWCHART_PREPARATION,
}


def _rgb(hex_value: str) -> RGBColor:
    return RGBColor.from_string(hex_value)


def _set_text(shape, text: str, size: float, color: str, bold: bool = False) -> None:
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, Emu(2 * PX))
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)


def _arrow(connector) -> None:
    ln = connector.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")


def render_pptx(graph: FlowGraph) -> bytes:
    layout = compute_layout(graph)
    routed = route_edges(graph, layout)
    width, height = extent(layout, routed)
    height += TITLE_PX
    scale = min(1.0, MAX_SLIDE_EMU / (width * PX), MAX_SLIDE_EMU / (height * PX))

    def e(v: float) -> Emu:
        return Emu(int(v * PX * scale))

    prs = Presentation()
    prs.slide_width, prs.slide_height = e(width), e(height)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    font_k = max(0.5, scale)

    title = slide.shapes.add_textbox(e(20), e(8), e(width - 40), e(36))
    _set_text(title, graph.title, 20 * font_k, hex6("text"), bold=True)

    def y(v: float) -> float:
        return v + TITLE_PX

    for _, label, band in layout.lanes:
        rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, e(band.x), e(y(band.y)), e(band.w), e(band.h))
        rect.fill.solid()
        rect.fill.fore_color.rgb = _rgb(hex6("panel"))
        rect.line.color.rgb = _rgb(hex6("dim"))
        rect.line.width = Pt(0.75)
        rect.shadow.inherit = False
        _set_text(rect, label, 12 * font_k, hex6("text"), bold=True)
        rect.text_frame.vertical_anchor = MSO_ANCHOR.TOP

    shapes = {}
    notes: list[str] = []
    for n in graph.nodes:
        b = layout.boxes[n.id]
        shape = slide.shapes.add_shape(_SHAPES[n.type], e(b.x), e(y(b.y)), e(b.w), e(b.h))
        key = n.type.value
        shape.fill.solid()
        shape.fill.fore_color.rgb = _rgb(tint_hex(key, 0.82))
        shape.line.color.rgb = _rgb(hex6(key))
        shape.line.width = Pt(1.25)
        shape.shadow.inherit = False
        shape.name = f"node:{n.id}"
        _set_text(shape, n.label, 10 * font_k, hex6("text"))
        shapes[n.id] = shape
        if n.details():
            notes.append(f"[{n.id}] {n.label} - " + " | ".join(f"{k}: {v}" for k, v in n.details().items()))

    vertical = layout.direction == "TB"
    for r in routed:
        src, dst = shapes[r.edge.source], shapes[r.edge.target]
        (x1, y1), (x2, y2) = r.points[0], r.points[-1]
        conn = slide.shapes.add_connector(MSO_CONNECTOR.ELBOW, e(x1), e(y(y1)), e(x2), e(y(y2)))
        forward = r.points[0][1] < r.points[-1][1] if vertical else r.points[0][0] < r.points[-1][0]
        if vertical:
            begin, end = (2, 0) if forward else (3, 3)
        else:
            begin, end = (3, 1) if forward else (2, 2)
        conn.begin_connect(src, begin)
        conn.end_connect(dst, end)
        conn.line.color.rgb = _rgb(hex6("line"))
        conn.line.width = Pt(1.25)
        _arrow(conn)
        if r.edge.label:
            lx, ly = r.label_at
            w = 14 + 6.5 * min(len(r.edge.label), 24)
            box = slide.shapes.add_textbox(e(lx - w / 2), e(y(ly) - 10), e(w), e(20))
            box.fill.solid()
            box.fill.fore_color.rgb = _rgb(hex6("bg"))
            _set_text(box, r.edge.label[:24], 9 * font_k, hex6("dim"))

    if notes:
        slide.notes_slide.notes_text_frame.text = "\n".join(notes)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
