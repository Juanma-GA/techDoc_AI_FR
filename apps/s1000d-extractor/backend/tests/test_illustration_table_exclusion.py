import pytest


@pytest.mark.parametrize("reuse_image_outside_table", [False, True])
def test_table_illustration_is_not_exported_or_attached(
    tmp_path,
    reuse_image_outside_table: bool,
) -> None:
    import pymupdf as fitz

    from app.core.illustrations import attach_illustrations
    from app.core.structure_infer import build_ir
    from app.parsers.pdf_parser import parse_pdf

    pdf_path = tmp_path / "table-illustration.pdf"
    doc = fitz.open()
    page = doc.new_page()
    x0, y0, cell_width, row_height, columns, rows = 72, 90, 120, 70, 3, 3
    for row in range(rows + 1):
        page.draw_line(
            (x0, y0 + row * row_height),
            (x0 + columns * cell_width, y0 + row * row_height),
        )
    for column in range(columns + 1):
        page.draw_line(
            (x0 + column * cell_width, y0),
            (x0 + column * cell_width, y0 + rows * row_height),
        )

    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 96, 72))
    image.set_rect(image.irect, (255, 0, 0))
    image_rect = fitz.Rect(x0 + 12, y0 + 12, x0 + 100, y0 + 58)
    image_xref = page.insert_image(image_rect, pixmap=image)
    if reuse_image_outside_table:
        page.insert_image(fitz.Rect(72, 318, 160, 364), xref=image_xref)
    for row, label in enumerate(("Part number", "Description", "Quantity")):
        page.insert_text(
            (x0 + cell_width + 8, y0 + row * row_height + 35),
            label,
            fontsize=10,
        )
    page.insert_text(
        (72, 390 if reuse_image_outside_table else y0 + rows * row_height + 35),
        "Figure 7.1 Separate illustration",
        fontsize=11,
    )
    tables = page.find_tables().tables
    assert any(
        bbox[0] <= image_rect.x0
        and bbox[1] <= image_rect.y0
        and bbox[2] >= image_rect.x1
        and bbox[3] >= image_rect.y1
        for bbox in (table.bbox for table in tables)
    )
    doc.save(str(pdf_path))
    doc.close()

    root = build_ir(parse_pdf(pdf_path))
    figure = next(node for node in root.walk() if node.kind == "figure")
    out_dir = tmp_path / "images"

    assert attach_illustrations(
        root,
        pdf_path=str(pdf_path),
        out_dir=out_dir,
        doc_id="doc",
    ) == int(reuse_image_outside_table)
    if reuse_image_outside_table:
        assert figure.icn == "figure-7-1-separate-illustration.jpg"
        assert (out_dir / figure.icn).exists()
    else:
        assert figure.icn is None
        assert list(out_dir.iterdir()) == []
