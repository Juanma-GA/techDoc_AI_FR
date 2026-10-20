"""Parseur JSON (FlowGraph natif) et DSL texte compact.

DSL (une instruction par ligne, `#` = commentaire) :
    title: Traitement d'une non-conformite
    system: Vehicule - circuit de charge     # optionnel
    fault_code: P0562                        # optionnel
    direction: TB            # ou LR
    lane Qualite             # couloir courant pour les noeuds declares ensuite
    S [start] Debut
    D [decision] Conforme ?
    C [check] Mesurer tension batterie {ref: DM-24-00; attendu: 12,4 V; outils: multimetre}
    S -> A -> D              # chaine de liens
    D -> F : Oui             # lien etiquete
Details `{cle: valeur; ...}` : ref, attendu/expected, outils/tools, securite/warning, duree/duration.
Les noeuds cites dans un lien sans declaration sont crees (type process).
"""

from __future__ import annotations

import json
import re
from itertools import pairwise

from pydantic import ValidationError

from app.core.errors import AppError
from app.flow.model import Edge, FlowGraph, Lane, Node, coerce_node_type

_NODE_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*\[([^\]]+)\]\s*([^{]*?)\s*(?:\{(.*)\})?$")
_COMMENT_RE = re.compile(r"(^|\s)#.*$")
_EDGE_RE = re.compile(r"^([A-Za-z0-9_.-]+(?:\s*->\s*[A-Za-z0-9_.-]+)+)\s*(?::\s*(.*))?$")
_DETAIL_KEYS = {
    "ref": "ref",
    "reference": "ref",
    "expected": "expected",
    "attendu": "expected",
    "valeur": "expected",
    "tools": "tools",
    "outils": "tools",
    "outillage": "tools",
    "warning": "warning",
    "securite": "warning",
    "avertissement": "warning",
    "duration": "duration",
    "duree": "duration",
    "temps": "duration",
}
_DETAIL_MAX = {"ref": 120, "expected": 300, "tools": 300, "warning": 500, "duration": 40}
_HEADERS = {"system": "system", "systeme": "system", "fault_code": "fault_code", "code_defaut": "fault_code"}


def _details(raw: str, lineno: int, warnings: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in raw.split(";"):
        if not part.strip():
            continue
        key, sep, value = part.partition(":")
        field = _DETAIL_KEYS.get(key.strip().lower())
        if not sep or field is None:
            warnings.append(f"Ligne {lineno} : detail ignore '{part.strip()[:40]}'")
            continue
        if value.strip():
            out[field] = value.strip()[: _DETAIL_MAX[field]]
    return out


def _invalid(message: str, detail: object = None) -> AppError:
    return AppError("FLOW_INVALID", message, status_code=422, detail=detail)


def graph_from_dict(data: object) -> FlowGraph:
    try:
        return FlowGraph.model_validate(data)
    except ValidationError as exc:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        raise _invalid("Graphe invalide", errors) from exc


def parse_json(text: str) -> FlowGraph:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _invalid(f"JSON invalide ligne {exc.lineno} : {exc.msg}") from exc
    return graph_from_dict(data)


def parse_dsl(text: str) -> tuple[FlowGraph, list[str]]:
    warnings: list[str] = []
    title, direction = "Logigramme", "TB"
    lanes: list[Lane] = []
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    lane: str | None = None
    meta: dict[str, str] = {}

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = _COMMENT_RE.sub("", raw).strip()
        if not line:
            continue
        low = line.lower()
        head = low.split(":", 1)[0].strip()
        if low.startswith("title:"):
            title = line.split(":", 1)[1].strip() or title
        elif ":" in low and head in _HEADERS:
            meta[_HEADERS[head]] = line.split(":", 1)[1].strip()[: 200 if head.startswith("sys") else 60]
        elif low.startswith("direction:"):
            direction = "LR" if line.split(":", 1)[1].strip().upper() == "LR" else "TB"
        elif low.startswith("lane "):
            name = line[5:].strip()
            lane = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)[:64] or None
            if lane and all(item.id != lane for item in lanes):
                lanes.append(Lane(id=lane, label=name))
        elif m := _EDGE_RE.match(line):
            chain = [p.strip() for p in m.group(1).split("->")]
            label = (m.group(2) or "").strip()
            for src, dst in pairwise(chain):
                edges.append(Edge(source=src, target=dst, label=label))
            for nid in chain:
                nodes.setdefault(nid, Node(id=nid, label=nid, lane=lane))
        elif m := _NODE_RE.match(line):
            nid, ntype, label = m.group(1), m.group(2), m.group(3).strip() or m.group(1)
            extra = _details(m.group(4) or "", lineno, warnings)
            nodes[nid] = Node(id=nid, label=label, type=coerce_node_type(ntype), lane=lane, **extra)
        else:
            warnings.append(f"Ligne {lineno} ignoree : {line[:60]}")

    if not nodes:
        raise _invalid("Aucun noeud trouve dans le DSL")
    graph = graph_from_dict(
        {
            "title": title,
            "direction": direction,
            **meta,
            "lanes": [ln.model_dump() for ln in lanes],
            "nodes": [n.model_dump() for n in nodes.values()],
            "edges": [e.model_dump() for e in edges],
        }
    )
    return graph, warnings


def parse_json_or_dsl(text: str) -> tuple[FlowGraph, list[str]]:
    if text.lstrip().startswith("{"):
        return parse_json(text), []
    return parse_dsl(text)
