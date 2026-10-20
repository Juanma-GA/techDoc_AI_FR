"""Export BPMN 2.0 (XML + DI) : importable dans Camunda Modeler, bpmn.io, Signavio, Bizagi."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from app.flow.layout import compute_layout
from app.flow.model import FlowGraph, NodeType, base_shape
from app.flow.routing import route_edges

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
}
for _p, _u in NS.items():
    ET.register_namespace(_p, _u)

_TAGS: dict[NodeType, str] = {
    NodeType.start: "startEvent",
    NodeType.end: "endEvent",
    NodeType.process: "task",
    NodeType.io: "task",
    NodeType.document: "task",
    NodeType.decision: "exclusiveGateway",
    NodeType.subprocess: "subProcess",
    NodeType.connector: "intermediateThrowEvent",
    NodeType.check: "exclusiveGateway",
    NodeType.repair: "task",
    NodeType.safety: "task",
}
_EVENT_SIZE = 36
_GATEWAY_SIZE = 50


def _q(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


def _bpmn_id(node_id: str) -> str:
    return "N_" + node_id.replace(".", "_")


def _bounds(parent: ET.Element, x: float, y: float, w: float, h: float) -> None:
    ET.SubElement(parent, _q("dc", "Bounds"), x=f"{x:.0f}", y=f"{y:.0f}", width=f"{w:.0f}", height=f"{h:.0f}")


def render_bpmn(graph: FlowGraph) -> str:
    layout = compute_layout(graph)
    routed = route_edges(graph, layout)
    defs = ET.Element(
        _q("bpmn", "definitions"),
        id="Definitions_1",
        targetNamespace="urn:atexis:flowchart-generator",
        exporter="flowchart-generator",
        exporterVersion="0.1.0",
    )
    has_lanes = bool(layout.lanes)
    if has_lanes:
        collab = ET.SubElement(defs, _q("bpmn", "collaboration"), id="Collaboration_1")
        ET.SubElement(
            collab, _q("bpmn", "participant"), id="Participant_1", name=graph.title, processRef="Process_1"
        )
    process = ET.SubElement(
        defs, _q("bpmn", "process"), id="Process_1", name=graph.title, isExecutable="false"
    )

    if has_lanes:
        lane_set = ET.SubElement(process, _q("bpmn", "laneSet"), id="LaneSet_1")
        for lane_id, label, _ in layout.lanes:
            lane = ET.SubElement(lane_set, _q("bpmn", "lane"), id=f"Lane_{lane_id}", name=label)
            for n in graph.nodes:
                if (n.lane or "") == lane_id or (n.lane is None and lane_id == layout.lanes[0][0]):
                    ref = ET.SubElement(lane, _q("bpmn", "flowNodeRef"))
                    ref.text = _bpmn_id(n.id)

    incoming: dict[str, list[str]] = {}
    outgoing: dict[str, list[str]] = {}
    for i, e in enumerate(graph.edges):
        outgoing.setdefault(e.source, []).append(f"Flow_{i}")
        incoming.setdefault(e.target, []).append(f"Flow_{i}")
    for n in graph.nodes:
        attrs = {"id": _bpmn_id(n.id), "name": n.label}
        if n.type == NodeType.subprocess:
            attrs["triggeredByEvent"] = "false"
        el = ET.SubElement(process, _q("bpmn", _TAGS[n.type]), **attrs)
        details = n.details()
        if details:
            doc = ET.SubElement(el, _q("bpmn", "documentation"))
            doc.text = "\n".join(f"{k}: {v}" for k, v in details.items())
        for flow in incoming.get(n.id, []):
            ET.SubElement(el, _q("bpmn", "incoming")).text = flow
        for flow in outgoing.get(n.id, []):
            ET.SubElement(el, _q("bpmn", "outgoing")).text = flow
    for i, e in enumerate(graph.edges):
        attrs = {"id": f"Flow_{i}", "sourceRef": _bpmn_id(e.source), "targetRef": _bpmn_id(e.target)}
        if e.label:
            attrs["name"] = e.label
        ET.SubElement(process, _q("bpmn", "sequenceFlow"), **attrs)

    diagram = ET.SubElement(defs, _q("bpmndi", "BPMNDiagram"), id="Diagram_1")
    plane = ET.SubElement(
        diagram,
        _q("bpmndi", "BPMNPlane"),
        id="Plane_1",
        bpmnElement="Collaboration_1" if has_lanes else "Process_1",
    )
    if has_lanes:
        pool = ET.SubElement(
            plane,
            _q("bpmndi", "BPMNShape"),
            id="Participant_1_di",
            bpmnElement="Participant_1",
            isHorizontal="true" if layout.direction == "LR" else "false",
        )
        x1 = min(b.x for _, _, b in layout.lanes)
        y1 = min(b.y for _, _, b in layout.lanes)
        x2 = max(b.x + b.w for _, _, b in layout.lanes)
        y2 = max(b.y + b.h for _, _, b in layout.lanes)
        _bounds(pool, x1, y1, x2 - x1, y2 - y1)
        for lane_id, _, band in layout.lanes:
            shape = ET.SubElement(
                plane,
                _q("bpmndi", "BPMNShape"),
                id=f"Lane_{lane_id}_di",
                bpmnElement=f"Lane_{lane_id}",
                isHorizontal="true" if layout.direction == "LR" else "false",
            )
            _bounds(shape, band.x, band.y, band.w, band.h)
    for n in graph.nodes:
        b = layout.boxes[n.id]
        shape = ET.SubElement(
            plane, _q("bpmndi", "BPMNShape"), id=f"{_bpmn_id(n.id)}_di", bpmnElement=_bpmn_id(n.id)
        )
        if n.type in (NodeType.start, NodeType.end, NodeType.connector):
            s = _EVENT_SIZE
        elif base_shape(n.type) == NodeType.decision:
            s = _GATEWAY_SIZE
        else:
            _bounds(shape, b.x, b.y, b.w, b.h)
            continue
        _bounds(shape, b.cx - s / 2, b.cy - s / 2, s, s)
    for i, r in enumerate(routed):
        edge = ET.SubElement(plane, _q("bpmndi", "BPMNEdge"), id=f"Flow_{i}_di", bpmnElement=f"Flow_{i}")
        for x, y in r.points:
            ET.SubElement(edge, _q("di", "waypoint"), x=f"{x:.0f}", y=f"{y:.0f}")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(defs, encoding="unicode")
