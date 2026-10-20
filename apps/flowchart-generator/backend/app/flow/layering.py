"""Couches Sugiyama : arcs retour, rangs, noeuds virtuels, ordre et coordonnees transverses.

Les liens qui sautent plusieurs rangs sont decoupes en noeuds virtuels : chaque
branche occupe ainsi sa propre colonne et l'arbre de diagnostic se deploie en largeur.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.flow.model import Edge, FlowGraph, NodeType

_YES = ("oui", "yes", "ok", "vrai", "true", "conforme", "correct", "bon", "o", "y")
_SWEEPS = 6


@dataclass
class Layers:
    rank: dict[str, int]
    lane: dict[str, str]
    succ: dict[str, list[str]]
    pred: dict[str, list[str]]
    back: set[tuple[str, str]]
    dummies: set[str] = field(default_factory=set)
    chains: dict[int, list[str]] = field(default_factory=dict)
    order: dict[tuple[int, str], list[str]] = field(default_factory=dict)


def _priority(e: Edge) -> int:
    label = (e.label or "").strip().lower()
    return 0 if label.split(" ")[0] in _YES else 1


def back_edges(graph: FlowGraph) -> set[tuple[str, str]]:
    succ: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    indeg = {n.id: 0 for n in graph.nodes}
    for e in sorted(graph.edges, key=_priority):
        succ[e.source].append(e.target)
        indeg[e.target] += 1
    starts = [n.id for n in graph.nodes if n.type == NodeType.start or indeg[n.id] == 0]
    roots = starts + [n.id for n in graph.nodes if n.id not in starts]
    state: dict[str, int] = {}
    back: set[tuple[str, str]] = set()
    for root in roots:
        if root in state:
            continue
        stack: list[tuple[str, int]] = [(root, 0)]
        state[root] = 1
        while stack:
            nid, idx = stack[-1]
            if idx < len(succ[nid]):
                stack[-1] = (nid, idx + 1)
                nxt = succ[nid][idx]
                if state.get(nxt) == 1:
                    back.add((nid, nxt))
                elif nxt not in state:
                    state[nxt] = 1
                    stack.append((nxt, 0))
            else:
                state[nid] = 2
                stack.pop()
    return back


def _ranks(graph: FlowGraph, back: set[tuple[str, str]]) -> dict[str, int]:
    preds: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for e in graph.edges:
        if (e.source, e.target) not in back and e.source != e.target:
            preds[e.target].append(e.source)
    rank: dict[str, int] = {}
    for n in graph.nodes:
        stack = [n.id]
        while stack:
            nid = stack[-1]
            todo = [p for p in preds[nid] if p not in rank]
            if todo:
                stack.extend(todo)
                continue
            stack.pop()
            rank[nid] = max((rank[p] + 1 for p in preds[nid]), default=0)
    return rank


def build_layers(graph: FlowGraph, lane_of: dict[str, str]) -> Layers:
    back = back_edges(graph)
    rank = _ranks(graph, back)
    ids = [n.id for n in graph.nodes]
    ly = Layers(
        rank=rank, lane=dict(lane_of), succ={i: [] for i in ids}, pred={i: [] for i in ids}, back=back
    )
    indexed = sorted(enumerate(graph.edges), key=lambda ie: _priority(ie[1]))
    for idx, e in indexed:
        if (e.source, e.target) in back or e.source == e.target:
            continue
        prev, chain = e.source, []
        for r in range(rank[e.source] + 1, rank[e.target]):
            d = f"__d{idx}_{r}"
            rank[d], ly.lane[d], ly.succ[d], ly.pred[d] = r, lane_of[e.source], [], []
            ly.dummies.add(d)
            chain.append(d)
            ly.succ[prev].append(d)
            ly.pred[d].append(prev)
            prev = d
        ly.succ[prev].append(e.target)
        ly.pred[e.target].append(prev)
        ly.chains[idx] = chain
    _initial_order(graph, ly)
    _reduce_crossings(ly)
    return ly


def _initial_order(graph: FlowGraph, ly: Layers) -> None:
    """Parcours en profondeur : les sous-arbres restent groupes, la branche 'Oui' a gauche."""
    seen: dict[str, int] = {}
    roots = [n.id for n in graph.nodes if not ly.pred[n.id]] + [n.id for n in graph.nodes]
    for root in roots:
        stack = [root]
        while stack:
            nid = stack.pop()
            if nid in seen:
                continue
            seen[nid] = len(seen)
            stack.extend(reversed(ly.succ[nid]))
    for nid in sorted(seen, key=seen.get):
        ly.order.setdefault((ly.rank[nid], ly.lane[nid]), []).append(nid)


def _crossings(ly: Layers, lanes: list[str]) -> int:
    pos = {nid: (lanes.index(key[1]), i) for key, ids in ly.order.items() for i, nid in enumerate(ids)}
    by_rank: dict[int, list[tuple[tuple[int, int], tuple[int, int]]]] = {}
    for u, vs in ly.succ.items():
        for v in vs:
            by_rank.setdefault(ly.rank[u], []).append((pos[u], pos[v]))
    total = 0
    for edges in by_rank.values():
        for i, (a1, b1) in enumerate(edges):
            for a2, b2 in edges[i + 1 :]:
                if (a1 < a2 and b1 > b2) or (a1 > a2 and b1 < b2):
                    total += 1
    return total


def _reduce_crossings(ly: Layers) -> None:
    lanes = list(dict.fromkeys(ly.lane[n] for ids in ly.order.values() for n in ids))
    ranks = sorted({r for r, _ in ly.order})
    best, best_order = _crossings(ly, lanes), {k: list(v) for k, v in ly.order.items()}
    for sweep in range(_SWEEPS):
        down = sweep % 2 == 0
        neigh = ly.pred if down else ly.succ
        for r in ranks if down else reversed(ranks):
            for (rr, lane), ids in ly.order.items():
                if rr != r:
                    continue
                index = {
                    nid: i for (_r2, ln), lst in ly.order.items() if ln == lane for i, nid in enumerate(lst)
                }
                keys: dict[str, float] = {}
                for i, nid in enumerate(ids):
                    ps = [index[p] for p in neigh[nid] if p in index]
                    keys[nid] = sum(ps) / len(ps) if ps else float(i)
                ids.sort(key=keys.__getitem__)
        score = _crossings(ly, lanes)
        if score < best:
            best, best_order = score, {k: list(v) for k, v in ly.order.items()}
    ly.order = best_order


def assign_cross(ly: Layers, node_size: float, dummy_size: float, gap: float) -> dict[str, float]:
    """Centres transverses (repere local au couloir) : enfants sous parents, parents au-dessus."""

    def size(n: str) -> float:
        return dummy_size if n in ly.dummies else node_size

    def sep(a: str, b: str) -> float:
        both_real = a not in ly.dummies and b not in ly.dummies
        return (size(a) + size(b)) / 2 + (gap if both_real else gap / 2)

    x: dict[str, float] = {}
    for ids in ly.order.values():
        acc = 0.0
        for i, nid in enumerate(ids):
            acc = acc + sep(ids[i - 1], nid) if i else size(nid) / 2
            x[nid] = acc

    def place(ids: list[str], want: list[float]) -> None:
        left, right = list(want), list(want)
        for i in range(1, len(ids)):
            left[i] = max(want[i], left[i - 1] + sep(ids[i - 1], ids[i]))
        for i in range(len(ids) - 2, -1, -1):
            right[i] = min(want[i], right[i + 1] - sep(ids[i], ids[i + 1]))
        for i, nid in enumerate(ids):
            x[nid] = (left[i] + right[i]) / 2

    ranks = sorted({r for r, _ in ly.order})
    for sweep in range(_SWEEPS + 1):
        neigh = ly.pred if sweep % 2 == 0 else ly.succ
        for r in ranks if sweep % 2 == 0 else reversed(ranks):
            for (rr, _), ids in ly.order.items():
                if rr != r:
                    continue
                want = []
                for nid in ids:
                    ps = [x[p] for p in neigh[nid] if ly.lane[p] == ly.lane[nid]]
                    want.append(sum(ps) / len(ps) if ps else x[nid])
                place(ids, want)
    return x
