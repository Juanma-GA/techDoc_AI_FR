"""Routage orthogonal des liens et utilitaires texte, partages par les exporteurs."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from itertools import pairwise

from app.flow.layout import GAP_MAIN, NODE_H, NODE_W, Box, Layout
from app.flow.model import Edge, FlowGraph

Point = tuple[float, float]


@dataclass
class RoutedEdge:
    edge: Edge
    points: list[Point]
    label_at: Point


def wrap(label: str, width: int = 22, max_lines: int = 3) -> list[str]:
    lines = textwrap.wrap(label, width=width, break_long_words=True) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


class _Axes:
    """Repere generique : 'main' = sens du flux, 'cross' = transverse (TB : y/x, LR : x/y)."""

    def __init__(self, vertical: bool) -> None:
        self.v = vertical

    def pt(self, main: float, cross: float) -> Point:
        return (cross, main) if self.v else (main, cross)

    def main(self, b: Box) -> tuple[float, float]:
        return (b.y, b.y + b.h) if self.v else (b.x, b.x + b.w)

    def cross(self, b: Box) -> tuple[float, float]:
        return (b.x, b.x + b.w) if self.v else (b.y, b.y + b.h)

    def c(self, b: Box) -> float:
        return b.cx if self.v else b.cy

    def m(self, b: Box) -> float:
        return b.cy if self.v else b.cx


def _simplify(points: list[Point]) -> list[Point]:
    out: list[Point] = []
    for p in points:
        if out and abs(out[-1][0] - p[0]) < 0.5 and abs(out[-1][1] - p[1]) < 0.5:
            continue
        if len(out) >= 2:
            (x0, y0), (x1, y1) = out[-2], out[-1]
            if (abs(x0 - x1) < 0.5 and abs(x1 - p[0]) < 0.5) or (abs(y0 - y1) < 0.5 and abs(y1 - p[1]) < 0.5):
                out[-1] = p
                continue
        out.append(p)
    return out


def _forward(ax: _Axes, s: Box, t: Box, via: list[Box]) -> list[Point]:
    """Descend de rang en rang ; les changements de colonne se font dans l'inter-rang."""
    pts = [ax.pt(ax.main(s)[1], ax.c(s))]
    cur = ax.c(s)
    for nxt in [*via, t]:
        if abs(ax.c(nxt) - cur) >= 0.5:
            gap = ax.main(nxt)[0] - GAP_MAIN / 2 if nxt is t else ax.m(nxt) - (GAP_MAIN + _row(ax)) / 2
            pts += [ax.pt(gap, cur), ax.pt(gap, ax.c(nxt))]
            cur = ax.c(nxt)
    pts.append(ax.pt(ax.main(t)[0], cur))
    return _simplify(pts)


def _row(ax: _Axes) -> float:
    return NODE_H if ax.v else NODE_W


def _blocked_after(ax: _Axes, b: Box, others: list[Box]) -> bool:
    lo, hi = ax.main(b)
    edge = ax.cross(b)[1]
    return any(
        o is not b and ax.cross(o)[0] >= edge and ax.main(o)[0] < hi and ax.main(o)[1] > lo for o in others
    )


def _backward(ax: _Axes, s: Box, t: Box, obstacles: list[Box], offset: float) -> list[Point]:
    """Boucle de retour contournant par le cote droit (TB) / le bas (LR) tous les blocs traverses."""
    lo, hi = min(ax.main(t)[0], ax.main(s)[0]), max(ax.main(t)[1], ax.main(s)[1])
    span = [o for o in obstacles if ax.main(o)[1] >= lo - 1 and ax.main(o)[0] <= hi + 1]
    lane = max(ax.cross(o)[1] for o in [s, t, *span]) + 24 + offset
    if _blocked_after(ax, s, obstacles):
        out = ax.main(s)[1] + GAP_MAIN / 2 - 6 - offset / 4
        start = [ax.pt(ax.main(s)[1], ax.c(s)), ax.pt(out, ax.c(s)), ax.pt(out, lane)]
    else:
        start = [ax.pt(ax.m(s), ax.cross(s)[1]), ax.pt(ax.m(s), lane)]
    if _blocked_after(ax, t, obstacles):
        inn = ax.main(t)[0] - GAP_MAIN / 2 + 6 + offset / 4
        end = [ax.pt(inn, lane), ax.pt(inn, ax.c(t) + 12), ax.pt(ax.main(t)[0], ax.c(t) + 12)]
    else:
        end = [ax.pt(ax.m(t), lane), ax.pt(ax.m(t), ax.cross(t)[1])]
    return _simplify(start + end)


def _label_point(ax: _Axes, points: list[Point], back: bool) -> Point:
    if back:
        segs = list(pairwise(points))
        (x1, y1), (x2, y2) = max(segs, key=lambda ab: abs(ab[0][0] - ab[1][0]) + abs(ab[0][1] - ab[1][1]))
        return (x1 + x2) / 2, (y1 + y2) / 2
    (x0, y0), (x1, y1) = points[0], points[1]
    if len(points) >= 4 and abs((y1 - y0) if ax.v else (x1 - x0)) <= GAP_MAIN:
        (x1, y1), (x2, y2) = points[1], points[2]
        return (x1 + x2) / 2, (y1 + y2) / 2
    d = min(GAP_MAIN * 0.45, (abs(y1 - y0) if ax.v else abs(x1 - x0)) / 2)
    return (x0, y0 + d) if ax.v else (x0 + d, y0)


def route_edges(graph: FlowGraph, layout: Layout) -> list[RoutedEdge]:
    ax = _Axes(layout.direction == "TB")
    obstacles = list(layout.boxes.values()) + list(layout.dummy_boxes.values())
    routed: list[RoutedEdge] = []
    back_count = 0
    for idx, e in enumerate(graph.edges):
        s, t = layout.boxes[e.source], layout.boxes[e.target]
        forward = (e.source, e.target) not in layout.back_edges and (
            layout.ranks[e.target] > layout.ranks[e.source]
        )
        if forward:
            via = [Box(x - 0.5, y - 0.5, 1, 1) for x, y in layout.waypoints.get(idx, [])]
            pts = _forward(ax, s, t, via)
        else:
            pts = _backward(ax, s, t, obstacles, offset=(back_count % 4) * 12)
            back_count += 1
        routed.append(RoutedEdge(edge=e, points=pts, label_at=_label_point(ax, pts, not forward)))
    return routed


def extent(layout: Layout, routed: list[RoutedEdge]) -> tuple[float, float]:
    """Taille totale incluant les boucles de retour qui debordent a droite / en bas."""
    w, h = layout.width, layout.height
    for r in routed:
        for x, y in r.points:
            w, h = max(w, x + 30), max(h, y + 30)
    return w, h
