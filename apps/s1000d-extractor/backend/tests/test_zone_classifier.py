"""Detection des entetes / pieds recurrents (core, sans route)."""

from __future__ import annotations

from app.core.ir import RawBlock
from app.core.zone_classifier import classify_zones


def _block(text: str, page: int, y0: float, y1: float, ph: float = 800.0) -> RawBlock:
    return RawBlock(text=text, page=page, y0=y0, y1=y1, page_height=ph)


def test_running_header_and_footer_detected() -> None:
    blocks: list[RawBlock] = []
    for p in range(1, 4):  # 3 pages
        blocks.append(_block("ACME MANUAL REF-4521", p, y0=20, y1=32))     # entete
        blocks.append(_block("The pump supplies pressure.", p, y0=400, y1=420))  # corps
        blocks.append(_block(f"Page {p}", p, y0=770, y1=784))              # pied
    classify_zones(blocks)
    zones = {(b.text[:4], b.page): b.zone for b in blocks}
    assert zones[("ACME", 1)] == "header"
    assert zones[("ACME", 3)] == "header"
    assert zones[("Page", 2)] == "footer"
    assert zones[("The ", 1)] == "body"


def test_page_number_footer_single_page() -> None:
    blocks = [
        _block("1 Description", 1, y0=100, y1=120),
        _block("12", 1, y0=775, y1=788),  # numero de page seul en bas
    ]
    classify_zones(blocks)
    assert blocks[0].zone == "body"   # le titre n'est PAS un entete (mono-page)
    assert blocks[1].zone == "footer"


def test_no_geometry_is_noop() -> None:
    # DOCX / OCR : pas de bbox -> aucune classification, tout reste body.
    blocks = [RawBlock(text="ACME MANUAL", page=1), RawBlock(text="ACME MANUAL", page=2)]
    classify_zones(blocks)
    assert all(b.zone == "body" for b in blocks)


def test_first_heading_not_tagged_header() -> None:
    # Un titre en haut de page qui n'apparait qu'une fois n'est pas un entete.
    blocks = [
        _block("1 Description", 1, y0=20, y1=40),
        _block("2 Procedure", 2, y0=20, y1=40),
    ]
    classify_zones(blocks)
    assert all(b.zone == "body" for b in blocks)
