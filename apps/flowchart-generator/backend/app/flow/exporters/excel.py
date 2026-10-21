"""Export Excel (.xlsx) : feuille `Logigramme` avec formes natives + feuille `Etapes` re-importable.

La feuille `Etapes` reprend les colonnes du parseur tabulaire (aller-retour possible).
"""

from __future__ import annotations

import io
import re
import zipfile

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.flow.exporters.excel_drawing import build_drawing
from app.flow.model import FlowGraph
from app.flow.theme import hex6

_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_DRAWING_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
_DRAWING_CT = "application/vnd.openxmlformats-officedocument.drawing+xml"
_SHEET = "xl/worksheets/sheet1.xml"
_SHEET_RELS = "xl/worksheets/_rels/sheet1.xml.rels"
_DETAIL_HEADERS = {
    "ref": "Reference",
    "expected": "Valeur attendue",
    "tools": "Outillage",
    "warning": "Securite",
    "duration": "Duree",
}


def _cell_safe(text: str) -> str:
    return re.sub(r"[;,|\n]+", " ", text).strip()


def _workbook(graph: FlowGraph) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Logigramme"
    ws["A1"] = graph.title
    ws["A1"].font = Font(bold=True, size=14, color=hex6("text"))
    ws.sheet_view.showGridLines = False

    steps = wb.create_sheet("Etapes")
    headers = ["ID", "Libelle", "Type", "Acteur", "Suivants", "Conditions", *_DETAIL_HEADERS.values()]
    steps.append(headers)
    head_fill = PatternFill("solid", fgColor=hex6("panel"))
    for c in steps[1]:
        c.font = Font(bold=True, color=hex6("text"))
        c.fill = head_fill
    lanes = {lane.id: lane.label for lane in graph.lanes}
    for n in graph.nodes:
        outs = [e for e in graph.edges if e.source == n.id]
        steps.append(
            [
                n.id,
                n.label,
                n.type.value,
                lanes.get(n.lane or "", ""),
                "; ".join(e.target for e in outs),
                "; ".join(_cell_safe(e.label) for e in outs) if any(e.label for e in outs) else "",
                *(getattr(n, f) or "" for f in _DETAIL_HEADERS),
            ]
        )
    for col, width in zip("ABCDEFGHIJK", (14, 48, 12, 20, 24, 24, 18, 24, 28, 36, 12), strict=True):
        steps.column_dimensions[col].width = width
    for row in steps.iter_rows(min_row=2):
        for idx in (1, 7, 8, 9):
            row[idx].alignment = Alignment(wrap_text=True, vertical="top")
    steps.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _inject(xlsx: bytes, drawing_xml: str) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(xlsx))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        names = src.namelist()
        for name in names:
            data = src.read(name)
            if name == _SHEET:
                text = data.decode("utf-8")
                root = re.search(r"<worksheet\b[^>]*>", text)
                if root and "xmlns:r=" not in root.group(0):
                    text = re.sub(r"<worksheet\b", f'<worksheet xmlns:r="{_REL_NS}"', text, count=1)
                text = text.replace("</worksheet>", '<drawing r:id="rIdFlow1"/></worksheet>')
                data = text.encode("utf-8")
            elif name == _SHEET_RELS:
                text = data.decode("utf-8").replace(
                    "</Relationships>",
                    f'<Relationship Id="rIdFlow1" Type="{_DRAWING_REL}" Target="../drawings/drawing1.xml"/>'
                    "</Relationships>",
                )
                data = text.encode("utf-8")
            elif name == "[Content_Types].xml":
                text = data.decode("utf-8").replace(
                    "</Types>",
                    f'<Override PartName="/xl/drawings/drawing1.xml" ContentType="{_DRAWING_CT}"/></Types>',
                )
                data = text.encode("utf-8")
            dst.writestr(name, data)
        if _SHEET_RELS not in names:
            dst.writestr(
                _SHEET_RELS,
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rIdFlow1" Type="{_DRAWING_REL}" Target="../drawings/drawing1.xml"/>'
                "</Relationships>",
            )
        dst.writestr("xl/drawings/drawing1.xml", drawing_xml)
    return out.getvalue()


def render_xlsx(graph: FlowGraph) -> bytes:
    drawing_xml, _, _ = build_drawing(graph)
    return _inject(_workbook(graph), drawing_xml)
