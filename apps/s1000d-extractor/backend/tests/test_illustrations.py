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
    first = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 24, 24))
    first.set_rect(first.irect, (255, 0, 0))
    second = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 24, 24))
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


def test_one_figure_can_keep_multiple_embedded_images(tmp_path) -> None:
    import fitz

    from app.core.illustrations import attach_illustrations
    from app.core.ir import IRNode

    pdf_path = tmp_path / "composite-figure.pdf"
    doc = fitz.open()
    page = doc.new_page()
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    for x, color in zip((72, 220, 320), colors):
        image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 24, 24))
        image.set_rect(image.irect, color)
        page.insert_image(fitz.Rect(x, 90, x + 80, 180), pixmap=image)
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

    assert attach_illustrations(root, pdf_path=str(pdf_path), out_dir=out_dir, doc_id="doc") == 3
    assert figures[0].icns == ["figure-5-3-first-panel.jpg"]
    assert figures[1].icns == [
        "figure-5-4-composite-panel.jpg",
        "figure-5-4-composite-panel-2.jpg",
    ]


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
