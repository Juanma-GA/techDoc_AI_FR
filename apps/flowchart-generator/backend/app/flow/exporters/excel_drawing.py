"""Construction du part DrawingML (xl/drawings/drawing1.xml) pour l'export Excel.

openpyxl ne sait pas creer de formes : on genere ici des `xdr:sp` natifs
(prstGeom flowChart*, polylignes custGeom flechees, zones de texte).
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from app.flow.layout import compute_layout
from app.flow.model import FlowGraph, NodeType
from app.flow.routing import RoutedEdge, extent, route_edges
from app.flow.theme import hex6, tint_hex

PX = 9525
TOP_PX = 40
XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"

_PRST: dict[NodeType, str] = {
    NodeType.start: "flowChartTerminator",
    NodeType.end: "flowChartTerminator",
    NodeType.process: "flowChartProcess",
    NodeType.decision: "flowChartDecision",
    NodeType.io: "flowChartInputOutput",
    NodeType.document: "flowChartDocument",
    NodeType.subprocess: "flowChartPredefinedProcess",
    NodeType.connector: "flowChartConnector",
    NodeType.check: "flowChartDecision",
    NodeType.repair: "flowChartProcess",
    NodeType.safety: "flowChartPreparation",
}


def _emu(v: float) -> int:
    return round(v * PX)


def _fill(hex_value: str | None) -> str:
    return f'<a:solidFill><a:srgbClr val="{hex_value}"/></a:solidFill>' if hex_value else "<a:noFill/>"


def _ln(hex_value: str, width_pt: float, arrow: bool = False, dash: bool = False) -> str:
    extra = '<a:prstDash val="dash"/>' if dash else ""
    tail = '<a:tailEnd type="triangle" w="med" len="med"/>' if arrow else ""
    return f'<a:ln w="{int(width_pt * 12700)}">{_fill(hex_value)}{extra}{tail}</a:ln>'


def _txbody(text: str, size_pt: float, color: str, anchor: str = "ctr", bold: bool = False) -> str:
    if not text:
        return ""
    b = ' b="1"' if bold else ""
    return (
        f'<xdr:txBody><a:bodyPr vertOverflow="clip" wrap="square" lIns="18000" tIns="18000" rIns="18000" '
        f'bIns="18000" rtlCol="0" anchor="{anchor}"/><a:lstStyle/><a:p><a:pPr algn="ctr"/>'
        f'<a:r><a:rPr lang="fr-FR" sz="{int(size_pt * 100)}"{b}>{_fill(color)}</a:rPr>'
        f"<a:t>{escape(text)}</a:t></a:r></a:p></xdr:txBody>"
    )


class _Drawing:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.next_id = 2

    def shape(
        self, name: str, x: float, y: float, w: float, h: float, geom: str, sp_pr: str, body: str = ""
    ) -> None:
        sid = self.next_id
        self.next_id += 1
        off, ext = (
            f'<a:off x="{_emu(x)}" y="{_emu(y)}"/>',
            f'<a:ext cx="{max(_emu(w), 1)}" cy="{max(_emu(h), 1)}"/>',
        )
        self.parts.append(
            f'<xdr:absoluteAnchor><xdr:pos x="{_emu(x)}" y="{_emu(y)}"/>'
            f'<xdr:ext cx="{max(_emu(w), 1)}" cy="{max(_emu(h), 1)}"/>'
            f'<xdr:sp macro="" textlink=""><xdr:nvSpPr><xdr:cNvPr id="{sid}" name="{escape(name)}"/>'
            f"<xdr:cNvSpPr/></xdr:nvSpPr><xdr:spPr><a:xfrm>{off}{ext}</a:xfrm>{geom}{sp_pr}</xdr:spPr>"
            f"{body}</xdr:sp><xdr:clientData/></xdr:absoluteAnchor>"
        )

    def polyline(self, name: str, points: list[tuple[float, float]], color: str) -> None:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        x0, y0 = min(xs), min(ys)
        w, h = max(max(xs) - x0, 0.1), max(max(ys) - y0, 0.1)
        cmds = "".join(
            f'<a:{"moveTo" if i == 0 else "lnTo"}><a:pt x="{_emu(px - x0)}" y="{_emu(py - y0)}"/>'
            f"</a:{'moveTo' if i == 0 else 'lnTo'}>"
            for i, (px, py) in enumerate(points)
        )
        geom = (
            "<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/>"
            '<a:rect l="0" t="0" r="r" b="b"/>'
            f'<a:pathLst><a:path w="{max(_emu(w), 1)}" h="{max(_emu(h), 1)}" fill="none">'
            f"{cmds}</a:path></a:pathLst>"
            "</a:custGeom>"
        )
        self.shape(name, x0, y0, w, h, geom, "<a:noFill/>" + _ln(color, 1.25, arrow=True))

    def xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<xdr:wsDr xmlns:xdr="{XDR}" xmlns:a="{A}">' + "".join(self.parts) + "</xdr:wsDr>"
        )


def _prst(name: str) -> str:
    return f'<a:prstGeom prst="{name}"><a:avLst/></a:prstGeom>'


def build_drawing(graph: FlowGraph) -> tuple[str, float, float]:
    """Retourne (xml, largeur_px, hauteur_px) ; les formes commencent a TOP_PX sous la ligne de titre."""
    layout = compute_layout(graph)
    routed: list[RoutedEdge] = route_edges(graph, layout)
    width, height = extent(layout, routed)
    d = _Drawing()

    for lane_id, label, band in layout.lanes:
        d.shape(
            f"lane:{lane_id}",
            band.x,
            band.y + TOP_PX,
            band.w,
            band.h,
            _prst("rect"),
            _fill(hex6("panel")) + _ln(hex6("dim"), 0.75, dash=True),
            _txbody(label, 11, hex6("text"), anchor="t", bold=True),
        )
    for r in routed:
        pts = [(x, y + TOP_PX) for x, y in r.points]
        d.polyline(f"edge:{r.edge.source}->{r.edge.target}", pts, hex6("line"))
    for r in routed:
        if r.edge.label:
            lx, ly = r.label_at
            w = 14 + 6.5 * min(len(r.edge.label), 24)
            d.shape(
                "label",
                lx - w / 2,
                ly - 10 + TOP_PX,
                w,
                20,
                _prst("rect"),
                _fill(hex6("bg")) + "<a:ln><a:noFill/></a:ln>",
                _txbody(r.edge.label[:24], 9, hex6("dim")),
            )
    for n in graph.nodes:
        b = layout.boxes[n.id]
        key = n.type.value
        d.shape(
            f"node:{n.id}",
            b.x,
            b.y + TOP_PX,
            b.w,
            b.h,
            _prst(_PRST[n.type]),
            _fill(tint_hex(key, 0.82)) + _ln(hex6(key), 1.25),
            _txbody(n.label, 10, hex6("text")),
        )
    return d.xml(), width, height + TOP_PX
