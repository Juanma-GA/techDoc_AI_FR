"""Export draw.io / diagrams.net (.drawio) : formes flowchart natives, liens orthogonaux.

Le fichier s'ouvre dans draw.io desktop / web et peut y etre converti en .vsdx (Visio).
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from app.flow.layout import compute_layout
from app.flow.model import FlowGraph, NodeType
from app.flow.routing import extent, route_edges
from app.flow.theme import css, tint_hex

_STYLES: dict[NodeType, str] = {
    NodeType.start: "shape=mxgraph.flowchart.terminator;",
    NodeType.end: "shape=mxgraph.flowchart.terminator;",
    NodeType.process: "rounded=0;",
    NodeType.decision: "rhombus;",
    NodeType.io: "shape=parallelogram;perimeter=parallelogramPerimeter;fixedSize=1;size=14;",
    NodeType.document: "shape=document;boundedLbl=1;size=0.2;",
    NodeType.subprocess: "shape=process;backgroundOutline=1;size=0.06;",
    NodeType.connector: "ellipse;aspect=fixed;",
    NodeType.check: "rhombus;",
    NodeType.repair: "rounded=0;",
    NodeType.safety: "shape=hexagon;perimeter=hexagonPerimeter2;size=0.15;fixedSize=0;",
}


def render_drawio(graph: FlowGraph) -> str:
    layout = compute_layout(graph)
    routed = route_edges(graph, layout)
    width, height = extent(layout, routed)
    mxfile = ET.Element("mxfile", host="flowchart-generator", type="device")
    diagram = ET.SubElement(mxfile, "diagram", id="flow", name=graph.title[:60])
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="0",
        dy="0",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="1",
        pageScale="1",
        pageWidth=f"{width:.0f}",
        pageHeight=f"{height:.0f}",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    horizontal = "0" if layout.direction == "LR" else "1"
    for lane_id, label, band in layout.lanes:
        cell = ET.SubElement(
            root,
            "mxCell",
            id=f"lane_{lane_id}",
            value=label,
            vertex="1",
            parent="1",
            style=(
                f"swimlane;horizontal={horizontal};startSize=30;html=1;whiteSpace=wrap;"
                f"fillColor={css('panel')};strokeColor={css('dim')};fontColor={css('text')};"
                "swimlaneFillColor=none;"
            ),
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=f"{band.x}",
            y=f"{band.y}",
            width=f"{band.w}",
            height=f"{band.h}",
            **{"as": "geometry"},
        )

    for n in graph.nodes:
        b = layout.boxes[n.id]
        key = n.type.value
        style = (
            f"{_STYLES[n.type]}whiteSpace=wrap;html=1;strokeWidth=1.5;"
            f"fillColor=#{tint_hex(key, 0.82)};strokeColor={css(key)};fontColor={css('text')};"
        )
        details = n.details()
        if details:
            tip = "\n".join(f"{k}: {v}" for k, v in details.items())
            holder = ET.SubElement(root, "object", id=f"n_{n.id}", label=n.label, tooltip=tip, **details)
            cell = ET.SubElement(holder, "mxCell", style=style, vertex="1", parent="1")
        else:
            cell = ET.SubElement(
                root, "mxCell", id=f"n_{n.id}", value=n.label, style=style, vertex="1", parent="1"
            )
        ET.SubElement(
            cell, "mxGeometry", x=f"{b.x}", y=f"{b.y}", width=f"{b.w}", height=f"{b.h}", **{"as": "geometry"}
        )

    for i, r in enumerate(routed):
        cell = ET.SubElement(
            root,
            "mxCell",
            id=f"e_{i}",
            value=r.edge.label,
            edge="1",
            parent="1",
            source=f"n_{r.edge.source}",
            target=f"n_{r.edge.target}",
            style=(
                "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;html=1;endArrow=block;endFill=1;"
                f"strokeColor={css('line')};fontColor={css('dim')};labelBackgroundColor={css('bg')};"
            ),
        )
        geo = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        if len(r.points) > 2:
            arr = ET.SubElement(geo, "Array", **{"as": "points"})
            for x, y in r.points[1:-1]:
                ET.SubElement(arr, "mxPoint", x=f"{x}", y=f"{y}")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(mxfile, encoding="unicode")
