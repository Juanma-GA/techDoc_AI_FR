"""Parser PDF : geometrie (bbox), zones, detection de tableaux."""

from __future__ import annotations

import pathlib
import tempfile


def _write(data: bytes, name: str) -> str:
    p = pathlib.Path(tempfile.gettempdir()) / name
    p.write_bytes(data)
    return str(p)


def test_blocks_carry_geometry(pdf_bytes) -> None:
    from app.parsers.pdf_parser import parse_pdf_pages

    pages = parse_pdf_pages(_write(pdf_bytes, "geo.pdf"))
    blocks = [b for p in pages for b in p.blocks]
    assert blocks
    geo = [b for b in blocks if b.y0 is not None and b.page_height]
    assert geo, "aucun bloc ne porte de geometrie (bbox)"


def test_table_detected(pdf_bytes_table) -> None:
    from app.parsers.pdf_parser import parse_pdf_pages

    pages = parse_pdf_pages(_write(pdf_bytes_table, "tbl.pdf"))
    blocks = [b for p in pages for b in p.blocks]
    tables = [b for b in blocks if b.is_table and b.table_rows]
    assert tables, "aucun tableau detecte par find_tables"
    rows = tables[0].table_rows
    assert any("M6" in c for r in rows for c in r)
