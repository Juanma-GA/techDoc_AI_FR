"""Placement en couches : les branches se deploient en colonnes, sans chevauchement."""

from __future__ import annotations

import pytest

from app.flow.layout import Box, compute_layout
from app.flow.parsers.json_dsl import parse_dsl
from app.flow.routing import route_edges

DSL = """title: Batterie
direction: {direction}
{lane_a}
S [start] Voyant batterie allume
SEC [safety] Consigner le vehicule
C1 [check] Tension OK ?
C2 [decision] Courroie OK ?
{lane_b}
R0 [repair] Remplacer la courroie
R1 [repair] Remplacer l'alternateur
{lane_a}
V [check] Essai OK ?
end [end] Panne resolue
S -> SEC -> C1
C1 -> V : Oui
C1 -> C2 : Non
C2 -> R1 : Oui
C2 -> R0 : Non
R0 -> V
R1 -> V
V -> end : Oui
V -> C1 : Non
"""


def _graph(direction: str = "TB", lanes: bool = False):
    text = DSL.format(
        direction=direction,
        lane_a="lane Technicien" if lanes else "",
        lane_b="lane Atelier" if lanes else "",
    )
    graph, _ = parse_dsl(text)
    return graph


def _overlap(a: Box, b: Box) -> bool:
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


@pytest.mark.parametrize("direction", ["TB", "LR"])
def test_branches_spread_in_columns(direction: str) -> None:
    layout = compute_layout(_graph(direction))
    b = layout.boxes
    cross = (lambda n: b[n].cx) if direction == "TB" else (lambda n: b[n].cy)
    assert cross("C2") != pytest.approx(cross("V"))
    assert cross("R0") != pytest.approx(cross("R1"))
    assert layout.ranks["C1"] < layout.ranks["C2"] < layout.ranks["R0"] < layout.ranks["V"]


@pytest.mark.parametrize("direction", ["TB", "LR"])
@pytest.mark.parametrize("lanes", [False, True])
def test_no_overlap_and_routes_stay_orthogonal(direction: str, lanes: bool) -> None:
    graph = _graph(direction, lanes)
    layout = compute_layout(graph)
    boxes = list(layout.boxes.values())
    for i, a in enumerate(boxes):
        for c in boxes[i + 1 :]:
            assert not _overlap(a, c)
    for r in route_edges(graph, layout):
        for (x1, y1), (x2, y2) in zip(r.points, r.points[1:], strict=False):
            assert abs(x1 - x2) < 0.5 or abs(y1 - y2) < 0.5
    if lanes:
        assert len(layout.lanes) == 2
