from __future__ import annotations


def test_image_without_figure_caption_is_saved_as_pictogram(tmp_path) -> None:
    import pymupdf as fitz

    from app.core.illustrations import attach_illustrations
    from app.core.ir import IRNode

    pdf_path = tmp_path / "figure-and-decoration.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 45), "1 Description", fontsize=18)

    figure_image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 80))
    figure_image.set_rect(figure_image.irect, (0, 120, 220))
    page.insert_image(fitz.Rect(72, 85, 252, 205), pixmap=figure_image)
    page.insert_text((72, 222), "Figure 1 Overview", fontsize=11)

    decoration = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 80))
    decoration.set_rect(decoration.irect, (220, 120, 0))
    page.insert_image(fitz.Rect(320, 300, 500, 430), pixmap=decoration)
    doc.save(str(pdf_path))
    doc.close()

    figure = IRNode(id="figure", kind="figure", text="Figure 1 Overview", page=1)
    chapter = IRNode(
        id="chapter",
        kind="section",
        text="1 Description",
        page=1,
        children=[figure],
    )
    root = IRNode(id="root", kind="section", children=[chapter])
    out_dir = tmp_path / "images"

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc").saved_count == 2
    pictograms = [node for node in root.walk() if node.is_pictogram]

    assert figure.icn == "figure-1-overview.jpg"
    assert len(pictograms) == 1
    assert pictograms[0].icn == "picto_chapitre_1.jpg"
    assert pictograms[0] in chapter.children
    assert len(list(out_dir.glob("*.jpg"))) == 2
    assert not list(out_dir.glob("illustration-*.jpg"))
