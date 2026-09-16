"""Decoupage multi-DM selon le niveau."""

from __future__ import annotations

from app.core.ir import IRNode
from app.core.splitter import split_into_dms


def _doc() -> IRNode:
    root = IRNode(id="r", kind="section", level=0)
    ch0 = IRNode(id="c0", kind="section", text="0 Description", level=1)
    s01 = IRNode(id="s01", kind="section", text="0.1 Function", level=2)
    s02 = IRNode(id="s02", kind="section", text="0.2 Brake", level=2)
    ch0.children = [s01, s02]
    ch1 = IRNode(id="c1", kind="section", text="1 Maintenance", level=1)
    s11 = IRNode(id="s11", kind="section", text="1.1 Clean", level=2)
    ch1.children = [s11]
    root.children = [ch0, ch1]
    return root


def test_chapter_level_two_dms() -> None:
    dms = split_into_dms(_doc(), "chapter")
    assert len(dms) == 2
    assert dms[0].title == "0 Description"
    assert dms[0].root.children[0].text == "0 Description"


def test_section_level_three_dms() -> None:
    dms = split_into_dms(_doc(), "section")
    assert len(dms) == 3
    assert {d.title for d in dms} == {"0.1 Function", "0.2 Brake", "1.1 Clean"}
    assert all(d.root.children[0].kind == "section" for d in dms)


def test_no_section_fallback_single_dm() -> None:
    root = IRNode(id="r", kind="section", level=0)
    root.children = [IRNode(id="p", kind="paragraph", text="x")]
    dms = split_into_dms(root, "section")
    assert len(dms) == 1
