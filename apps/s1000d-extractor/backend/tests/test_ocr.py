"""Conversion markdown OCR -> blocs IR (offline, sans appel Mistral)."""

from __future__ import annotations

import logging
from typing import cast

from sqlalchemy.orm import Session

from app.core import ingest, ocr
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


def test_mixed_pdf_ocr_processes_only_scanned_pages(tmp_path, monkeypatch, caplog) -> None:
    import fitz

    pdf_path = tmp_path / "mixed.pdf"
    source = fitz.open()
    for page_number in range(1, 5):
        page = source.new_page()
        if page_number in (1, 3):
            page.insert_text((72, 72), f"Page {page_number} has searchable content.")
    source.save(str(pdf_path))
    source.close()

    seen: dict[str, int] = {}

    class FakeClient:
        def ocr_pdf(self, pdf_bytes: bytes) -> list[str]:
            selected = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                seen["page_count"] = selected.page_count
            finally:
                selected.close()
            return ["# Scanned page 2", "# Scanned page 4"]

    monkeypatch.setattr(ocr, "ocr_available", lambda _db: True)
    monkeypatch.setattr(ocr.MistralClient, "from_db", lambda _db: FakeClient())

    progress: list[tuple[str, int]] = []
    with caplog.at_level(logging.INFO, logger="s1000d_extractor.ingest"):
        blocks = ingest.extract_blocks(
            pdf_path,
            fmt="pdf",
            db=cast(Session, object()),
            progress_cb=lambda step, pct: progress.append((step, pct)),
        )

    assert seen["page_count"] == 2
    assert "pdf_parse_timing" in caplog.text
    assert "pdf_ocr_timing" in caplog.text
    assert "Searchable content" not in caplog.text
    assert "Scanned page" not in caplog.text
    assert progress == [
        ("parse", 15),
        ("parse", 20),
        ("parse", 25),
        ("parse", 30),
        ("ocr", 30),
    ]
    assert [(block.page, block.text) for block in blocks if block.page in (2, 4)] == [
        (2, "Scanned page 2"),
        (4, "Scanned page 4"),
    ]
