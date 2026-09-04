"""Resolveur : la meme forme -> des candidats differents selon le contexte."""

from __future__ import annotations

from app.core.ir import IRNode
from app.core.resolver import candidates_for


def _list(context: str, form: str = "bullet") -> IRNode:
    return IRNode(id="x", kind="item-sequence", form=form, context=context)


def test_bullet_list_descriptive_maps_to_randomlist() -> None:
    cands = candidates_for(_list("descriptive"))
    assert cands[0].element == "randomList"


def test_ordered_list_descriptive_maps_to_sequentiallist() -> None:
    cands = candidates_for(_list("descriptive", "ordered"))
    assert cands[0].element == "sequentialList"


def test_bullet_list_procedural_maps_to_proceduralstep() -> None:
    cands = candidates_for(_list("procedural"))
    assert cands[0].element == "proceduralStep"


def test_unknown_context_exposes_both_candidates() -> None:
    cands = candidates_for(_list("unknown"))
    elements = {c.element for c in cands}
    assert "randomList" in elements and "proceduralStep" in elements


def test_admonition_maps_to_warning() -> None:
    node = IRNode(id="w", kind="admonition", admonition="warning", context="procedural")
    assert candidates_for(node)[0].element == "warning"
