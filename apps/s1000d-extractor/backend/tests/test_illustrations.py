"""Extraction des illustrations (JPG) + ICN sur les figures + expo API."""

from __future__ import annotations


def _upload(client, data: bytes) -> str:
    r = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", data)},
        data={"s1000d_issue": "5.0", "context_hint": "mixed"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_slugify() -> None:
    from app.core.illustrations import slugify

    assert slugify("Figure 1 Hydraulic pump location").startswith("figure-1-hydraulic")
    assert slugify("") == "illustration"


def test_rename_illustration_to_icn_png(tmp_path) -> None:
    import fitz

    from app.core.illustrations import rename_illustration

    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8))
    pixmap.set_rect(pixmap.irect, (255, 0, 0))
    pixmap.save(str(tmp_path / "figure-4-1.jpg"))

    name = rename_illustration(
        tmp_path,
        "figure-4-1.jpg",
        "ICN-WEG-AA0004-00001-A-02.png",
    )

    assert name == "ICN-WEG-AA0004-00001-A-02.png"
    assert not (tmp_path / "figure-4-1.jpg").exists()
    assert (tmp_path / name).read_bytes().startswith(b"\x89PNG")


def test_embedded_rgb_jpeg_is_preserved_without_reencoding(tmp_path, monkeypatch) -> None:
    import hashlib
    import fitz

    from app.core.illustrations import _image_digest, _save_pixmap

    source_path = tmp_path / "source.jpg"
    source_pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 32, 24))
    source_pixmap.set_rect(source_pixmap.irect, (25, 120, 220))
    source_pixmap.save(str(source_path), jpg_quality=70)
    source_bytes = source_path.read_bytes()

    pdf_path = tmp_path / "embedded-jpeg.pdf"
    doc = fitz.open()
    doc.new_page().insert_image(fitz.Rect(72, 72, 200, 168), stream=source_bytes)
    doc.save(str(pdf_path))
    doc.close()

    embedded = fitz.open(str(pdf_path))
    xref = embedded[0].get_image_info(xrefs=True)[0]["xref"]
    extracted = embedded.extract_image(xref)
    destination = tmp_path / "output.jpg"

    def fail_if_decoded(*_args, **_kwargs):
        raise AssertionError("An embedded JPEG should not be decoded to pixels.")

    monkeypatch.setattr(fitz, "Pixmap", fail_if_decoded)

    assert _image_digest(embedded, xref) == hashlib.sha256(extracted["image"]).hexdigest()
    assert _save_pixmap(embedded, xref, destination) is True
    assert extracted["ext"] in {"jpg", "jpeg"}
    assert destination.read_bytes() == extracted["image"]
    embedded.close()


def test_small_page_icon_does_not_replace_real_figure_image(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.ir import IRNode

    pdf_path = tmp_path / "figure-with-page-icon.pdf"
    doc = fitz.open()
    page = doc.new_page()
    icon = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 32, 32))
    icon.set_rect(icon.irect, (255, 220, 0))
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 90))
    image.set_rect(image.irect, (0, 120, 220))
    page.insert_image(fitz.Rect(72, 40, 120, 88), pixmap=icon)
    page.insert_image(fitz.Rect(72, 120, 312, 300), pixmap=image)
    page.insert_text((72, 320), "Figure 6.2 Real figure", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    figure = IRNode(id="figure", kind="figure", text="Figure 6.2 Real figure", page=1)
    root = IRNode(id="root", kind="section", children=[figure])
    out_dir = tmp_path / "images"

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc") == 1
    assert figure.is_pictogram is False
    assert figure.icn == "figure-6-2-real-figure.jpg"
    assert len(list(out_dir.glob("*.jpg"))) == 1


def test_single_image_figure_keeps_red_cross_overlay(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.ir import IRNode

    pdf_path = tmp_path / "figure-with-cross.pdf"
    doc = fitz.open()
    page = doc.new_page()
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100))
    image.set_rect(image.irect, (80, 120, 160))
    page.insert_image(fitz.Rect(72, 50, 220, 220), pixmap=image)
    page.insert_text((112, 190), "X", fontsize=72, fontname="hebo", color=(1, 0, 0))
    page.insert_text((72, 240), "Figure 5.2 Incorrect stacking", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    figure = IRNode(id="figure", kind="figure", text="Figure 5.2 Incorrect stacking", page=1)
    root = IRNode(id="root", kind="section", children=[figure])
    out_dir = tmp_path / "images"

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc") == 1
    assert figure.icn == "figure-5-2-incorrect-stacking.jpg"
    pixmap = fitz.Pixmap(str(out_dir / figure.icn))
    samples = pixmap.samples
    channels = pixmap.n
    red_pixels = sum(
        1
        for index in range(0, len(samples) - channels + 1, channels)
        if samples[index] > 160 and samples[index + 1] < 100 and samples[index + 2] < 100
    )

    assert red_pixels > 100


def test_multiple_dmrl_icns_are_applied_in_figure_order(tmp_path) -> None:
    from app.core.dmrl import DmrlEntry
    from app.core.illustrations import rename_illustration
    from app.core.ir import IRNode
    from app.core.splitter import DmUnit
    from app.core.wizard import _apply_dmrl_icns

    figures = [
        IRNode(id="f1", kind="figure", icn="figure-4-1.jpg"),
        IRNode(id="f2", kind="figure", icn="figure-4-2.jpg"),
    ]
    for figure in figures:
        (tmp_path / figure.icn).write_bytes(b"image")
    unit = DmUnit(
        dm_id="dm1",
        title="Description",
        root=IRNode(id="root", kind="section", children=figures),
        dmrl_index=0,
    )

    _apply_dmrl_icns(
        [unit],
        [DmrlEntry(icn="ICN-WEG-AA0004-00001-A-02.jpg\nICN-WEG-AA0004-00002-A-02.jpg")],
        tmp_path,
    )

    assert [figure.icn for figure in figures] == [
        "ICN-WEG-AA0004-00001-A-02.jpg",
        "ICN-WEG-AA0004-00002-A-02.jpg",
    ]
    assert rename_illustration(
        tmp_path,
        "ICN-WEG-AA0004-00001-A-02.jpg",
        "ICN-WEG-AA0004-00001-A-02.jpg",
    ) == "ICN-WEG-AA0004-00001-A-02.jpg"


def test_dmrl_icn_replaces_generated_figure_name(tmp_path) -> None:
    from app.core.dmrl import DmrlEntry
    from app.core.ir import IRNode
    from app.core.splitter import DmUnit
    from app.core.wizard import _apply_dmrl_icns

    figure = IRNode(
        id="f1",
        kind="figure",
        icn="figure-4-1-serrage-correct.jpg",
        icns=["figure-4-1-serrage-correct.jpg"],
    )
    (tmp_path / figure.icn).write_bytes(b"image")
    unit = DmUnit(
        dm_id="dm1",
        title="Description",
        root=IRNode(id="root", kind="section", children=[figure]),
        dmrl_index=0,
    )

    _apply_dmrl_icns(
        [unit],
        [DmrlEntry(icn="ICN-WEG-AA0007-00001-A-02.jpg")],
        tmp_path,
    )

    assert figure.icn == "ICN-WEG-AA0007-00001-A-02.jpg"
    assert figure.icns == ["ICN-WEG-AA0007-00001-A-02.jpg"]
    assert (tmp_path / figure.icn).exists()
    assert not (tmp_path / "figure-4-1-serrage-correct.jpg").exists()


def test_two_figures_on_one_line_keep_image_alignment(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.structure_infer import build_ir
    from app.parsers.pdf_parser import parse_pdf

    pdf_path = tmp_path / "two-figures.pdf"
    doc = fitz.open()
    page = doc.new_page()
    first = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80))
    first.set_rect(first.irect, (255, 0, 0))
    second = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80))
    second.set_rect(second.irect, (0, 0, 255))
    page.insert_image(fitz.Rect(72, 90, 168, 186), pixmap=first)
    page.insert_image(fitz.Rect(220, 90, 316, 186), pixmap=second)
    page.insert_text(
        (72, 210),
        "Figure 4.1 Serrage correct Figure 4.2 Serrage incorrect",
        fontsize=11,
    )
    doc.save(str(pdf_path))
    doc.close()

    root = build_ir(parse_pdf(pdf_path))
    figures = [node for node in root.walk() if node.kind == "figure"]
    out_dir = tmp_path / "images"

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc") == 2
    assert [figure.text for figure in figures] == [
        "Figure 4.1 Serrage correct",
        "Figure 4.2 Serrage incorrect",
    ]
    assert [figure.icn for figure in figures] == [
        "figure-4-1-serrage-correct.jpg",
        "figure-4-2-serrage-incorrect.jpg",
    ]


def test_caption_overlap_does_not_assign_image_to_next_figure(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.ir import IRNode

    pdf_path = tmp_path / "caption-overlap.pdf"
    doc = fitz.open()
    page = doc.new_page()
    first = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80))
    first.set_rect(first.irect, (255, 0, 0))
    second = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80))
    second.set_rect(second.irect, (0, 0, 255))
    page.insert_image(fitz.Rect(72, 90, 168, 186), pixmap=first)
    page.insert_image(fitz.Rect(220, 90, 316, 186), pixmap=second)
    page.insert_text((72, 194), "Figure 4.10 First image", fontsize=11)
    page.insert_text((220, 194), "Figure 4.11 Second image", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    figures = [
        IRNode(id="f1", kind="figure", text="Figure 4.10 First image", page=1),
        IRNode(id="f2", kind="figure", text="Figure 4.11 Second image", page=1),
    ]
    root = IRNode(id="root", kind="section", children=figures)
    out_dir = tmp_path / "images"

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc") == 2
    assert [figure.icn for figure in figures] == [
        "figure-4-10-first-image.jpg",
        "figure-4-11-second-image.jpg",
    ]


def test_one_figure_can_keep_multiple_embedded_images(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.ir import IRNode

    pdf_path = tmp_path / "composite-figure.pdf"
    doc = fitz.open()
    page = doc.new_page()
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    for x, color in zip((72, 220, 320), colors):
        image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80))
        image.set_rect(image.irect, color)
        page.insert_image(fitz.Rect(x, 90, x + 80, 180), pixmap=image)
    page.draw_line((225, 95), (305, 175), color=(1, 0, 0), width=3)
    page.insert_text((302, 130), "Panel label", fontsize=8)
    page.insert_text((72, 205), "Figure 5.3 First panel", fontsize=11)
    page.insert_text((220, 205), "Figure 5.4 Composite panel", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    figures = [
        IRNode(id="f1", kind="figure", text="Figure 5.3 First panel", page=1),
        IRNode(id="f2", kind="figure", text="Figure 5.4 Composite panel", page=1),
    ]
    root = IRNode(id="root", kind="section", children=figures)
    out_dir = tmp_path / "images"

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc") == 2
    assert figures[0].icns == ["figure-5-3-first-panel.jpg"]
    assert figures[1].icns == [
        "figure-5-4-composite-panel.jpg",
    ]
    composite = fitz.Pixmap(str(out_dir / figures[1].icn))
    assert composite.width > 220
    assert any(
        red > 180 and green < 120 and blue < 120
        for x in range(composite.width)
        for y in range(composite.height)
        for red, green, blue in [composite.pixel(x, y)]
    )


def test_vector_figure_is_rasterized_when_pdf_has_no_embedded_image(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.structure_infer import build_ir
    from app.parsers.pdf_parser import parse_pdf

    pdf_path = tmp_path / "vector-figure.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 60), "1 Description", fontsize=18, fontname="hebo")
    page.draw_rect(
        fitz.Rect(72, 90, 300, 220),
        color=(0, 0, 0),
        fill=(0.8, 0.8, 0.8),
        width=2,
    )
    page.draw_line((90, 110), (280, 200), color=(1, 0, 0), width=3)
    page.insert_text((560, 130), "LANG", fontsize=9, rotate=90)
    page.insert_text((72, 250), "Figure 1 Vector nameplate", fontsize=11)
    assert not page.get_images(full=True)
    doc.save(str(pdf_path))
    doc.close()

    root = build_ir(parse_pdf(pdf_path))
    figure = next(node for node in root.walk() if node.kind == "figure")
    out_dir = tmp_path / "images"

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc") == 1
    assert figure.icn == "figure-1-vector-nameplate.jpg"
    image = fitz.Pixmap(str(out_dir / figure.icn))
    assert image.width > 100
    assert image.height > 200


def test_large_pictogram_without_caption_is_attached_to_chapter(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.ir import IRNode

    pdf_path = tmp_path / "pictogram.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 60), "6 Description", fontsize=18, fontname="hebo")
    pictogram = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64))
    pictogram.set_rect(pictogram.irect, (255, 220, 0))
    for coordinate in range(20, 44):
        pictogram.set_pixel(coordinate, coordinate, (0, 0, 0))
        pictogram.set_pixel(coordinate, 63 - coordinate, (0, 0, 0))
    page.insert_image(fitz.Rect(72, 100, 232, 260), pixmap=pictogram)
    doc.save(str(pdf_path))
    doc.close()

    chapter = IRNode(id="chapter", kind="section", text="6 Description", page=1)
    root = IRNode(id="root", kind="section", children=[chapter])
    out_dir = tmp_path / "images"

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc") == 1
    pictos = [node for node in root.walk() if node.is_pictogram]
    assert len(pictos) == 1
    assert pictos[0].text == "Picto chapitre 6"
    assert pictos[0].icn == "picto_chapitre_6.jpg"
    assert (out_dir / pictos[0].icn).exists()

    from app.core.ir import from_dict, to_dict

    restored = from_dict(to_dict(root))
    assert next(node for node in restored.walk() if node.is_pictogram).icn == pictos[0].icn


def test_pictogram_replaces_unmatched_figure_caption(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.ir import IRNode

    pdf_path = tmp_path / "pictogram-caption.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 60), "6 Description", fontsize=18, fontname="hebo")
    pictogram = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64))
    pictogram.set_rect(pictogram.irect, (255, 220, 0))
    for coordinate in range(20, 44):
        pictogram.set_pixel(coordinate, coordinate, (0, 0, 0))
    page.insert_image(fitz.Rect(72, 100, 232, 260), pixmap=pictogram)
    page.insert_text((72, 280), "Figure 6.2 Attention", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    figure = IRNode(id="figure", kind="figure", text="Figure 6.2 Attention", page=1)
    chapter = IRNode(id="chapter", kind="section", text="6 Description", page=1, children=[figure])
    root = IRNode(id="root", kind="section", children=[chapter])
    out_dir = tmp_path / "images"

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc") == 1
    assert figure.is_pictogram is True
    assert figure.text == "Picto chapitre 6"
    assert figure.icn == "picto_chapitre_6.jpg"
    assert len([node for node in root.walk() if node.kind == "figure"]) == 1


def test_pictogram_uses_dm_root_instead_of_nested_subsection(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.ir import IRNode

    pdf_path = tmp_path / "nested-pictogram.pdf"
    doc = fitz.open()
    page = doc.new_page()
    pictogram = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64))
    pictogram.set_rect(pictogram.irect, (255, 220, 0))
    for coordinate in range(20, 44):
        pictogram.set_pixel(coordinate, coordinate, (0, 0, 0))
    page.insert_image(fitz.Rect(72, 100, 232, 260), pixmap=pictogram)
    doc.save(str(pdf_path))
    doc.close()

    subsection = IRNode(id="subsection", kind="section", text="6.1.1 Details", level=3, page=1)
    dm_section = IRNode(
        id="dm-section",
        kind="section",
        text="6.1 Description",
        level=2,
        page=1,
        children=[subsection],
    )
    root = IRNode(
        id="root",
        kind="section",
        children=[IRNode(id="chapter", kind="section", text="6 Chapter", level=1, children=[dm_section])],
    )
    out_dir = tmp_path / "images"

    assert attach_illustrations(
        root,
        pdf_path=str(pdf_path),
        out_dir=out_dir,
        doc_id="doc",
        dm_level=2,
    ) == 1
    picto = next(node for node in root.walk() if node.is_pictogram)
    assert picto.text == "Picto chapitre 6_1"
    assert picto in dm_section.children
    assert picto not in subsection.children


def test_images_extracted_and_served(client, pdf_bytes_image) -> None:
    doc_id = _upload(client, pdf_bytes_image)
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")

    names = client.get(f"/api/v1/documents/{doc_id}/wizard/images").json()
    assert names, "aucune illustration extraite"
    # Nommee d'apres la legende 'Figure 1 ...'.
    assert any(n.startswith("figure-1") for n in names)

    r = client.get(f"/api/v1/documents/{doc_id}/wizard/images/{names[0]}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"

    # Traversee de repertoire refusee.
    bad = client.get(f"/api/v1/documents/{doc_id}/wizard/images/..%2Fsecret.jpg")
    assert bad.status_code == 404


def test_figure_icn_in_generated_xml(client, pdf_bytes_image) -> None:
    doc_id = _upload(client, pdf_bytes_image)
    client.post(f"/api/v1/documents/{doc_id}/wizard/start")
    # split -> type -> structure -> generate
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"types": {}})
    client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={"overrides": []})
    st = client.post(f"/api/v1/documents/{doc_id}/wizard/advance", json={}).json()
    assert st["step"] == "generate"
    found = False
    for d in st["dms"]:
        xml = client.get(f"/api/v1/documents/{doc_id}/wizard/dm/{d['dm_id']}/xml").text
        graphic_lines = [line for line in xml.splitlines() if "<graphic " in line]
        if any('infoEntityIdent="figure-1' in line and ".jpg" not in line for line in graphic_lines):
            found = True
    assert found, "l'ICN de la figure n'est pas referencee dans le XML"
