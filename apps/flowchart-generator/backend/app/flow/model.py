"""Modele de graphe normalise : pivot unique entre parseurs et exporteurs."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class NodeType(StrEnum):
    start = "start"
    end = "end"
    process = "process"
    decision = "decision"
    io = "io"
    document = "document"
    subprocess = "subprocess"
    connector = "connector"
    # Types metier depannage / maintenance industrielle
    check = "check"  # controle, mesure, inspection avec resultat (losange)
    repair = "repair"  # action corrective : remplacer, regler, reparer (rectangle)
    safety = "safety"  # consigne de securite / consignation, ISO 5807 "preparation" (hexagone)


_BASE_SHAPE: dict[NodeType, NodeType] = {NodeType.check: NodeType.decision, NodeType.repair: NodeType.process}


def base_shape(node_type: NodeType) -> NodeType:
    """Forme geometrique a dessiner (les types metier reutilisent les formes ISO 5807)."""
    return _BASE_SHAPE.get(node_type, node_type)


_TYPE_ALIASES: dict[str, NodeType] = {
    "debut": NodeType.start,
    "start": NodeType.start,
    "begin": NodeType.start,
    "fin": NodeType.end,
    "end": NodeType.end,
    "stop": NodeType.end,
    "action": NodeType.process,
    "process": NodeType.process,
    "tache": NodeType.process,
    "task": NodeType.process,
    "etape": NodeType.process,
    "step": NodeType.process,
    "decision": NodeType.decision,
    "test": NodeType.decision,
    "condition": NodeType.decision,
    "io": NodeType.io,
    "entree": NodeType.io,
    "sortie": NodeType.io,
    "data": NodeType.io,
    "input": NodeType.io,
    "output": NodeType.io,
    "donnee": NodeType.io,
    "document": NodeType.document,
    "doc": NodeType.document,
    "subprocess": NodeType.subprocess,
    "sous-processus": NodeType.subprocess,
    "sous_processus": NodeType.subprocess,
    "predefined": NodeType.subprocess,
    "connector": NodeType.connector,
    "connecteur": NodeType.connector,
    "renvoi": NodeType.connector,
    "check": NodeType.check,
    "controle": NodeType.check,
    "mesure": NodeType.check,
    "measure": NodeType.check,
    "inspection": NodeType.check,
    "verification": NodeType.check,
    "diagnostic": NodeType.check,
    "repair": NodeType.repair,
    "reparation": NodeType.repair,
    "remplacement": NodeType.repair,
    "replace": NodeType.repair,
    "corrective": NodeType.repair,
    "intervention": NodeType.repair,
    "reglage": NodeType.repair,
    "adjust": NodeType.repair,
    "safety": NodeType.safety,
    "securite": NodeType.safety,
    "warning": NodeType.safety,
    "avertissement": NodeType.safety,
    "consignation": NodeType.safety,
    "lockout": NodeType.safety,
    "preparation": NodeType.safety,
}

DETAIL_FIELDS: tuple[str, ...] = ("ref", "expected", "tools", "warning", "duration")

_ACCENTS = str.maketrans("éèêëàâäîïôöùûüç", "eeeeaaaiioouuuc")
_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def coerce_node_type(raw: str | None) -> NodeType:
    """Type tolerant (FR/EN, accents, casse) ; defaut `process`."""
    key = (raw or "").strip().lower().translate(_ACCENTS)
    return _TYPE_ALIASES.get(key, NodeType.process)


class Lane(BaseModel):
    id: str
    label: str


class Node(BaseModel):
    id: str
    label: str = Field(max_length=500)
    type: NodeType = NodeType.process
    lane: str | None = None
    # Details maintenance (optionnels) : reference doc/tache, valeur attendue,
    # outillage, avertissement securite, duree estimee.
    ref: str | None = Field(default=None, max_length=120)
    expected: str | None = Field(default=None, max_length=300)
    tools: str | None = Field(default=None, max_length=300)
    warning: str | None = Field(default=None, max_length=500)
    duration: str | None = Field(default=None, max_length=40)

    def details(self) -> dict[str, str]:
        return {k: v for k in DETAIL_FIELDS if (v := getattr(self, k))}

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError(f"identifiant de noeud invalide : {v!r}")
        return v

    @field_validator("type", mode="before")
    @classmethod
    def _coerce_type(cls, v: object) -> NodeType:
        return v if isinstance(v, NodeType) else coerce_node_type(str(v))


class Edge(BaseModel):
    source: str
    target: str
    label: str = Field(default="", max_length=200)


class FlowGraph(BaseModel):
    title: str = Field(default="Logigramme", max_length=200)
    direction: str = Field(default="TB", pattern="^(TB|LR)$")
    system: str | None = Field(default=None, max_length=200)  # equipement / sous-systeme
    fault_code: str | None = Field(default=None, max_length=60)  # code defaut / symptome
    lanes: list[Lane] = Field(default_factory=list)
    nodes: list[Node] = Field(min_length=1, max_length=500)
    edges: list[Edge] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def _check_refs(self) -> FlowGraph:
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            dup = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"identifiants de noeuds dupliques : {', '.join(dup)}")
        known = set(ids)
        for e in self.edges:
            if e.source not in known or e.target not in known:
                raise ValueError(f"lien vers un noeud inconnu : {e.source} -> {e.target}")
        lane_ids = {lane.id for lane in self.lanes}
        for n in self.nodes:
            if n.lane and n.lane not in lane_ids:
                self.lanes.append(Lane(id=n.lane, label=n.lane))
                lane_ids.add(n.lane)
        return self


def slug_id(text: str, used: set[str]) -> str:
    """Genere un identifiant stable et unique a partir d'un libelle."""
    base = re.sub(r"[^A-Za-z0-9]+", "_", text.translate(_ACCENTS)).strip("_")[:24] or "N"
    candidate, i = base, 2
    while candidate in used:
        candidate, i = f"{base}_{i}", i + 1
    used.add(candidate)
    return candidate
