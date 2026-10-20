"""Placement en couches (Sugiyama) avec couloirs (swimlanes).

Pur Python, sans Graphviz. Etapes (cf. ``layering``) :
1. retrait des arcs retour (boucles) par DFS ;
2. rang = plus long chemin depuis les sources ;
3. noeuds virtuels sur les liens longs -> chaque branche a sa colonne ;
4. ordre intra-rang par balayages barycentriques (minimisation des croisements) ;
5. coordonnees transverses (parents centres sur leurs enfants) puis projection
   (TB : couloirs en colonnes, LR : en bandes).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.flow.layering import assign_cross, build_layers
from app.flow.model import FlowGraph

Point = tuple[float, float]
DUMMY_SIZE = 16

NODE_W, NODE_H = 170, 64
GAP_MAIN, GAP_CROSS = 56, 40
LANE_HEADER, MARGIN = 34, 20
_DEFAULT_LANE = "__default__"


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass
class Layout:
    width: float
    height: float
    direction: str
    boxes: dict[str, Box] = field(default_factory=dict)
    lanes: list[tuple[str, str, Box]] = field(default_factory=list)
    ranks: dict[str, int] = field(default_factory=dict)
    back_edges: set[tuple[str, str]] = field(default_factory=set)
    # index du lien dans graph.edges -> centres des noeuds virtuels traverses
    waypoints: dict[int, list[Point]] = field(default_factory=dict)
    # boites des noeuds virtuels (pour l'evitement des boucles de retour)
    dummy_boxes: dict[str, Box] = field(default_factory=dict)


def compute_layout(graph: FlowGraph) -> Layout:
    lane_order = [lane.id for lane in graph.lanes] or [_DEFAULT_LANE]
    known = set(lane_order)
    lane_of = {n.id: (n.lane if n.lane in known else lane_order[0]) for n in graph.nodes}
    vertical = graph.direction == "TB"
    node_cross = NODE_W if vertical else NODE_H
    ly = build_layers(graph, lane_of)
    xs = assign_cross(ly, node_cross, DUMMY_SIZE, GAP_CROSS)

    def half(nid: str) -> float:
        return (DUMMY_SIZE if nid in ly.dummies else node_cross) / 2

    lanes_shown = bool(graph.lanes)
    header = LANE_HEADER if lanes_shown else 0
    step_main = (NODE_H if vertical else NODE_W) + GAP_MAIN
    real_ranks = {nid: r for nid, r in ly.rank.items() if nid not in ly.dummies}
    max_rank = max(ly.rank.values()) if ly.rank else 0
    main_len = header + GAP_MAIN / 2 + (max_rank + 1) * step_main

    layout = Layout(width=0, height=0, direction=graph.direction, ranks=real_ranks, back_edges=ly.back)
    cross0 = float(MARGIN)
    centre: dict[str, float] = {}
    for lane in lane_order:
        members = [nid for nid, ln in ly.lane.items() if ln == lane]
        lo = min((xs[n] - half(n) for n in members), default=0.0)
        hi = max((xs[n] + half(n) for n in members), default=float(node_cross))
        size = (hi - lo) + 2 * GAP_CROSS
        for n in members:
            centre[n] = cross0 + GAP_CROSS + xs[n] - lo
        label = next((ln.label for ln in graph.lanes if ln.id == lane), "")
        band = Box(cross0, MARGIN, size, main_len) if vertical else Box(MARGIN, cross0, main_len, size)
        if lanes_shown:
            layout.lanes.append((lane, label, band))
        cross0 += size

    def box(nid: str) -> Box:
        m = MARGIN + header + GAP_MAIN / 2 + ly.rank[nid] * step_main
        if nid in ly.dummies:
            mc = m + (NODE_H if vertical else NODE_W) / 2
            d = DUMMY_SIZE
            cc = centre[nid]
            return Box(cc - d / 2, mc - d / 2, d, d) if vertical else Box(mc - d / 2, cc - d / 2, d, d)
        c = centre[nid] - node_cross / 2
        return Box(c, m, NODE_W, NODE_H) if vertical else Box(m, c, NODE_W, NODE_H)

    for n in graph.nodes:
        layout.boxes[n.id] = box(n.id)
    for d in ly.dummies:
        layout.dummy_boxes[d] = box(d)
    for idx, chain in ly.chains.items():
        layout.waypoints[idx] = [(layout.dummy_boxes[d].cx, layout.dummy_boxes[d].cy) for d in chain]

    total_cross = cross0 + MARGIN
    total_main = MARGIN * 2 + main_len
    layout.width, layout.height = (total_cross, total_main) if vertical else (total_main, total_cross)
    return layout
