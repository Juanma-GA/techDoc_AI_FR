"""Conversion markdown OCR -> blocs IR (offline, sans appel Mistral)."""

from __future__ import annotations

from app.core.ocr import markdown_to_blocks


def test_headings_and_paragraph() -> None:
    md = "# Description\n\nThe system supplies pressure.\n\n## Details\nText here."
    blocks = markdown_to_blocks(md, page=1)
    assert blocks[0].heading_level == 1 and blocks[0].text == "Description"
    assert any(b.text == "The system supplies pressure." and b.heading_level is None for b in blocks)
    assert any(b.heading_level == 2 for b in blocks)


def test_lists() -> None:
    md = "- Pump\n- Reservoir\n\n1. Disconnect\n2. Loosen"
    blocks = markdown_to_blocks(md)
    kinds = [b.list_kind for b in blocks]
    assert "bullet" in kinds and "ordered" in kinds


def test_table() -> None:
    md = "| Item | Qty |\n| --- | --- |\n| Bolt | 4 |"
    blocks = markdown_to_blocks(md)
    tables = [b for b in blocks if b.is_table]
    assert len(tables) == 1
    assert tables[0].table_rows == [["Item", "Qty"], ["Bolt", "4"]]
