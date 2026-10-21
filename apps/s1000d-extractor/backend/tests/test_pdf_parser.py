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


def test_parse_pdf_pages_reports_each_completed_page(tmp_path) -> None:
    import fitz

    from app.parsers.pdf_parser import parse_pdf_pages

    pdf_path = tmp_path / "progress.pdf"
    doc = fitz.open()
    for page_number in range(1, 4):
        page = doc.new_page()
        if page_number != 2:
            page.insert_text((72, 72), f"Searchable content on page {page_number}.")
    doc.save(str(pdf_path))
    doc.close()

    progress: list[tuple[int, int]] = []
    pages = parse_pdf_pages(
        pdf_path,
        progress_cb=lambda completed, total: progress.append((completed, total)),
    )

    assert progress == [(1, 3), (2, 3), (3, 3)]
    assert [page.has_text for page in pages] == [True, False, True]


def test_table_detected(pdf_bytes_table) -> None:
    from app.parsers.pdf_parser import parse_pdf_pages

    pages = parse_pdf_pages(_write(pdf_bytes_table, "tbl.pdf"))
    blocks = [b for p in pages for b in p.blocks]
    tables = [b for b in blocks if b.is_table and b.table_rows]
    assert tables, "aucun tableau detecte par find_tables"
    rows = tables[0].table_rows
    assert any("M6" in c for r in rows for c in r)


def test_large_red_crosses_over_images_do_not_pollute_figure_captions(tmp_path) -> None:
    import fitz

    from app.core.structure_infer import build_ir
    from app.parsers.pdf_parser import parse_pdf_pages

    pdf_path = tmp_path / "figure-crosses.pdf"
    doc = fitz.open()
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100))
    image.set_rect(image.irect, (80, 120, 160))

    first_page = doc.new_page()
    first_page.insert_image(fitz.Rect(72, 50, 260, 230), pixmap=image)
    first_page.insert_text((72, 230), "Figure 5.2 - Empilage incorrect", fontsize=10)
    first_page.insert_text((160, 230), "X", fontsize=72, fontname="hebo", color=(1, 0, 0))

    second_page = doc.new_page()
    second_page.insert_image(fitz.Rect(72, 50, 220, 220), pixmap=image)
    second_page.insert_image(fitz.Rect(260, 50, 408, 220), pixmap=image)
    second_page.insert_text((115, 210), "X", fontsize=72, fontname="hebo", color=(1, 0, 0))
    second_page.insert_text((303, 210), "X", fontsize=72, fontname="hebo", color=(1, 0, 0))
    second_page.insert_text(
        (72, 230),
        "Figure 5.3 - Correct stacking\nFigure 5.4 - Incorrect stacking",
        fontsize=10,
    )
    doc.save(str(pdf_path))
    doc.close()

    pages = parse_pdf_pages(pdf_path)
    root = build_ir([block for page in pages for block in page.blocks])

    assert [node.text for node in root.walk() if node.kind == "figure"] == [
        "Figure 5.2 - Empilage incorrect",
        "Figure 5.3 - Correct stacking",
        "Figure 5.4 - Incorrect stacking",
    ]


def test_red_cross_is_found_inside_caption_text_block() -> None:
    import fitz

    from app.core.pdf_overlays import large_red_cross_rects

    blocks = [{"lines": [{"spans": [
        {"text": "Figure 5.2 - Empilage incorrect", "bbox": (0, 80, 100, 90)},
        {"text": "X", "bbox": (35, 10, 85, 90), "size": 72, "color": 0xFF0000},
        {"text": "X", "bbox": (35, 10, 85, 90), "size": 72, "color": 0x000000},
    ]}]}]

    rects = large_red_cross_rects(blocks, [fitz.Rect(0, 0, 100, 100)])

    assert rects == [fitz.Rect(35, 10, 85, 90)]
