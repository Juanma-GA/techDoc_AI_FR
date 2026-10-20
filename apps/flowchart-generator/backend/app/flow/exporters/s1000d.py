"""Export S1000D : data module d'isolation de panne (faultIsolation, info code 421).

Structure inspiree de S1000D Issue 4.x (isolationStep / yesNoAnswer / listOfChoices /
isolationProcedureEnd). Le DMC est un code generique a renseigner : le fichier est un
point de depart a integrer dans un CSDB, pas un module valide contre le schema/BREX.
"""

from __future__ import annotations

import re
from collections import deque
from datetime import date
from xml.etree import ElementTree as ET

from app.flow.model import Edge, FlowGraph, Node, NodeType

_YES = {"oui", "yes", "o", "y", "ok", "vrai", "true", "conforme", "present", "presente"}
_NO = {"non", "no", "n", "nok", "ko", "faux", "false", "non conforme", "absent", "absente"}
_ENDS = (NodeType.end,)


def _xid(node_id: str) -> str:
    return "stp-" + re.sub(r"[^A-Za-z0-9_.-]", "_", node_id)


def _para(parent: ET.Element, text: str, tag: str = "para") -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def _order(graph: FlowGraph, out: dict[str, list[Edge]]) -> list[Node]:
    by_id = {n.id: n for n in graph.nodes}
    starts = [n.id for n in graph.nodes if n.type == NodeType.start] or [graph.nodes[0].id]
    seen: set[str] = set()
    order: list[Node] = []
    queue = deque(starts)
    while queue:
        nid = queue.popleft()
        if nid in seen:
            continue
        seen.add(nid)
        order.append(by_id[nid])
        queue.extend(e.target for e in out.get(nid, []))
    return order + [n for n in graph.nodes if n.id not in seen]


def _action(step: ET.Element, n: Node) -> None:
    action = ET.SubElement(step, "action")
    _para(action, n.label)
    if n.warning:
        _para(action, f"ATTENTION : {n.warning}")
    if n.tools:
        _para(action, f"Outillage : {n.tools}")
    if n.ref:
        _para(action, f"Reference : {n.ref}")
    if n.duration:
        _para(action, f"Duree estimee : {n.duration}")


def _answer(step: ET.Element, edges: list[Edge]) -> None:
    answer = ET.SubElement(step, "isolationStepAnswer")
    labels = [e.label.strip().lower() for e in edges]
    yes = [e for e, lb in zip(edges, labels, strict=True) if lb in _YES]
    no = [e for e, lb in zip(edges, labels, strict=True) if lb in _NO]
    if len(edges) == 2 and len(yes) == 1 and len(no) == 1:
        yn = ET.SubElement(answer, "yesNoAnswer")
        ET.SubElement(yn, "yesAnswer", nextActionRefId=_xid(yes[0].target))
        ET.SubElement(yn, "noAnswer", nextActionRefId=_xid(no[0].target))
        return
    choices = ET.SubElement(answer, "listOfChoices")
    for i, e in enumerate(edges, start=1):
        _para(choices, e.label or f"Choix {i}", "choice").set("nextActionRefId", _xid(e.target))


def _ident(root: ET.Element, graph: FlowGraph) -> None:
    today = date.today()
    ident = ET.SubElement(root, "identAndStatusSection")
    addr = ET.SubElement(ident, "dmAddress")
    dm_ident = ET.SubElement(addr, "dmIdent")
    ET.SubElement(
        dm_ident,
        "dmCode",
        modelIdentCode="ATEXIS",
        systemDiffCode="A",
        systemCode="00",
        subSystemCode="0",
        subSubSystemCode="0",
        assyCode="00",
        disassyCode="00",
        disassyCodeVariant="A",
        infoCode="421",
        infoCodeVariant="A",
        itemLocationCode="A",
    )
    ET.SubElement(dm_ident, "language", languageIsoCode="fr", countryIsoCode="FR")
    ET.SubElement(dm_ident, "issueInfo", issueNumber="001", inWork="01")
    items = ET.SubElement(addr, "dmAddressItems")
    ET.SubElement(
        items, "issueDate", year=f"{today.year}", month=f"{today.month:02d}", day=f"{today.day:02d}"
    )
    title = ET.SubElement(items, "dmTitle")
    _para(title, graph.system or "Systeme", "techName")
    _para(title, graph.title, "infoName")
    status = ET.SubElement(ident, "dmStatus", issueType="new")
    ET.SubElement(status, "security", securityClassification="01")
    ET.SubElement(status, "responsiblePartnerCompany", enterpriseCode="00000")
    ET.SubElement(status, "originator", enterpriseCode="00000")
    applic = ET.SubElement(ET.SubElement(status, "applic"), "displayText")
    _para(applic, "Toutes configurations", "simplePara")
    ET.SubElement(ET.SubElement(status, "qualityAssurance"), "unverified")


def _preliminary(proc: ET.Element, graph: FlowGraph) -> None:
    prelim = ET.SubElement(proc, "preliminaryRqmts")
    tools = sorted(
        {t.strip() for n in graph.nodes if n.tools for t in re.split(r"[;,]", n.tools) if t.strip()}
    )
    equips = ET.SubElement(prelim, "reqSupportEquips")
    if tools:
        group = ET.SubElement(equips, "supportEquipDescrGroup")
        for i, tool in enumerate(tools, start=1):
            _para(ET.SubElement(group, "supportEquipDescr", id=f"seq-{i:04d}"), tool, "name")
    else:
        ET.SubElement(equips, "noSupportEquips")
    warnings = [n.warning for n in graph.nodes if n.warning]
    warnings += [n.label for n in graph.nodes if n.type == NodeType.safety and not n.warning]
    safety = ET.SubElement(prelim, "reqSafety")
    if warnings:
        rqmts = ET.SubElement(safety, "safetyRqmts")
        for i, text in enumerate(dict.fromkeys(warnings), start=1):
            _para(ET.SubElement(rqmts, "warning", id=f"warn-{i:04d}"), text, "warningAndCautionPara")
    else:
        ET.SubElement(safety, "noSafety")


def render_s1000d(graph: FlowGraph) -> str:
    out: dict[str, list[Edge]] = {}
    for e in graph.edges:
        out.setdefault(e.source, []).append(e)
    root = ET.Element("dmodule")
    _ident(root, graph)
    proc = ET.SubElement(
        ET.SubElement(ET.SubElement(root, "content"), "faultIsolation"), "faultIsolationProcedure"
    )
    fault = ET.SubElement(proc, "fault", faultCode=graph.fault_code or "")
    descr = ET.SubElement(ET.SubElement(fault, "faultDescr"), "descr")
    start = next((n for n in graph.nodes if n.type == NodeType.start), None)
    descr.text = start.label if start else graph.title
    _preliminary(proc, graph)

    main = ET.SubElement(ET.SubElement(proc, "isolationProcedure"), "isolationMainProcedure")
    order = _order(graph, out)
    for idx, n in enumerate(order):
        edges = out.get(n.id, [])
        if n.type in _ENDS or not edges:
            _action(ET.SubElement(main, "isolationProcedureEnd", id=_xid(n.id)), n)
            continue
        step = ET.SubElement(main, "isolationStep", id=_xid(n.id))
        if len(edges) == 1:
            _action(step, n)
            nxt = order[idx + 1].id if idx + 1 < len(order) else None
            if edges[0].target != nxt:
                act = step.find("action")
                para = _para(act, "Passer a l'etape ") if act is not None else None
                if para is not None:
                    ET.SubElement(para, "internalRef", internalRefId=_xid(edges[0].target))
            continue
        if n.warning or n.tools or n.ref or n.duration:
            _action(step, n)
        question = n.label + (f" (attendu : {n.expected})" if n.expected else "")
        _para(ET.SubElement(step, "isolationStepQuestion"), question, "para")
        _answer(step, edges)
    ET.SubElement(proc, "closeRqmts")
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")
