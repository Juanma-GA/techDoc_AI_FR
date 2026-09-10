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


def test_rename_illustration_preserves_target_name_and_converts_png(tmp_path) -> None:
    import fitz

    source = tmp_path / "figure.jpg"
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8))
    pix.set_rect(pix.irect, (255, 0, 0))
    pix.save(str(source), jpg_quality=85)

    from app.core.illustrations import rename_illustration

    name = rename_illustration(tmp_path, source.name, "ICN-XX.png")

    assert name == "ICN-XX.png"
    assert not source.exists()
    assert (tmp_path / name).read_bytes().startswith(b"\x89PNG")


def test_dmrl_icns_are_applied_in_figure_order_and_collisions_are_suffixes(tmp_path) -> None:
    from app.core.dmrl import DmrlEntry
    from app.core.illustrations import rename_illustration
    from app.core.ir import IRNode
    from app.core.splitter import DmUnit
    from app.core.wizard import _apply_dmrl_icns

    figures = [
        IRNode(id="figure-1", kind="figure", icn="source-1.jpg"),
        IRNode(id="figure-2", kind="figure", icn="source-2.jpg"),
        IRNode(id="figure-3", kind="figure", icn="source-3.jpg"),
    ]
    for figure in figures:
        (tmp_path / figure.icn).write_bytes(b"image")

    unit = DmUnit(
        dm_id="dm1", title="Description",
        root=IRNode(id="root", kind="section", children=figures),
        dmrl_index=0,
    )
    _apply_dmrl_icns(
        [unit],
        [DmrlEntry(icn="ICN-FIRST.jpg\nICN-SECOND.jpg")],
        tmp_path,
    )

    assert [figure.icn for figure in figures] == [
        "ICN-FIRST.jpg", "ICN-SECOND.jpg", "source-3.jpg",
    ]
    (tmp_path / "ICN-COLLIDE.jpg").write_bytes(b"existing")
    (tmp_path / "source-collision.jpg").write_bytes(b"image")
    assert rename_illustration(tmp_path, "source-collision.jpg", "ICN-COLLIDE.jpg") == (
        "ICN-COLLIDE-2.jpg"
    )


def test_graphic_reference_omits_extension() -> None:
    from app.core.ir import IRNode
    from app.core.s1000d_serializer import serialize

    root = IRNode(
        id="root", kind="section", children=[
            IRNode(id="figure", kind="figure", text="Figure 1", icn="ICN-XX.jpg"),
        ],
    )

    xml = serialize(root, issue="5.0", dm_type="descriptive", title="Description")

    assert 'infoEntityIdent="ICN-XX"' in xml
    assert 'infoEntityIdent="ICN-XX.jpg"' not in xml


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
        if 'infoEntityIdent="figure-1' in xml:
            found = True
    assert found, "l'ICN de la figure n'est pas referencee dans le XML"
