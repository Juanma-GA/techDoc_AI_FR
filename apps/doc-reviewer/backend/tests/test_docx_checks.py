"""Checks Word natifs (Phase 2) : barres de révision + zones sémantiques."""

from __future__ import annotations

from app.checks import docx_checks
from app.core import docx_zones
from app.parsers.docx_parser import Block, ParsedDocx


def _parsed(blocks: list[Block]) -> ParsedDocx:
    return ParsedDocx(
        block_count=len(blocks),
        blocks=blocks,
        headers=[],
        footers=[],
        full_text="\n".join(b.text for b in blocks),
    )


def _block(idx: int, text: str, *, revision_kind: str | None = None, kind: str = "paragraph") -> Block:
    return Block(
        target_id=f"dp{idx}", index=idx, zone="body", kind=kind, text=text,
        revised=revision_kind is not None, revision_kind=revision_kind,
    )


def test_revision_bar_check_flags_tracked_changes() -> None:
    parsed = _parsed([
        _block(1, "Texte normal."),
        _block(2, "Texte insere suivi.", revision_kind="ins"),
        _block(3, "Texte supprime suivi.", revision_kind="del"),
    ])
    out = docx_checks.run(parsed)
    codes = {(r.rule_code, r.page) for r in out}
    assert ("DOCX_REVISION_BAR", 2) in codes
    assert ("DOCX_REVISION_BAR", 3) in codes
    # le bloc non revise n'est pas signale
    assert all(r.page != 1 for r in out)
    # detection-only
    assert all(r.proposed == "" for r in out)


def test_revision_bar_check_ignores_clean_doc() -> None:
    parsed = _parsed([_block(1, "Rien de suivi."), _block(2, "Toujours rien.")])
    assert docx_checks.run(parsed) == []


def test_recognize_zones_tags_semantic_regions() -> None:
    parsed = _parsed([
        _block(1, "RECORD OF REVISIONS", kind="heading"),
        _block(2, "rev A — 2024"),
        _block(3, "LIST OF EFFECTIVE PAGES", kind="heading"),
        _block(4, "page 1"),
    ])
    docx_zones.recognize_zones(parsed)
    by_target = {b.target_id: b.semantic_zone for b in parsed.blocks}
    assert by_target["dp1"] == "highlights_table"
    assert by_target["dp2"] == "highlights_table"
    assert by_target["dp3"] == "lep"
    assert by_target["dp4"] == "lep"
