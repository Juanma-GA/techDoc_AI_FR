"""ZIP export reference-index reuse tests."""

from types import SimpleNamespace

import pymupdf

from app.core import ir as ir_mod
from app.core import wizard_zip_export
from app.core.ir import IRNode


def test_zip_export_builds_one_shared_reference_index(monkeypatch) -> None:
    dms = [
        {
            "dm_id": "dm-1",
            "dmc": "DMC-TEST-A-00-00-00-00A-040A-A",
            "dm_type": "descriptive",
            "tree": ir_mod.to_dict(IRNode(id="root-1", kind="section")),
        },
        {
            "dm_id": "dm-2",
            "dmc": "DMC-TEST-A-00-00-00-00A-520A-A",
            "dm_type": "procedural",
            "tree": ir_mod.to_dict(IRNode(id="root-2", kind="section")),
        },
    ]
    monkeypatch.setattr(wizard_zip_export.ws, "load_dms", lambda _doc: dms)
    monkeypatch.setattr(wizard_zip_export.wres, "dmrl_entries", lambda _doc: [])
    indexes = []
    shared_index = {("figure", "1"): []}

    def build_index(documents):
        indexes.append(documents)
        return shared_index

    monkeypatch.setattr(wizard_zip_export, "build_reference_index", build_index)
    used_indexes = []

    def generate_dm(_doc, dm_id, *, db, reference_index):
        used_indexes.append(reference_index)
        return f"<dmodule id=\"{dm_id}\"/>"

    result = wizard_zip_export.generate_zip_dm_xmls(
        SimpleNamespace(s1000d_issue="4.2"),
        ["dm-1", "dm-2"],
        db=object(),
        dm_xml_generator=generate_dm,
    )

    assert len(indexes) == 1
    assert list(result) == ["dm-1", "dm-2"]
    assert used_indexes == [shared_index, shared_index]


def test_zip_images_resize_convert_and_separate_pictograms(
    tmp_path,
    monkeypatch,
) -> None:
    illustration = tmp_path / "figure-1.png"
    pictogram = tmp_path / "picto_chapitre_1.png"
    for path in (illustration, pictogram):
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 60))
        pixmap.clear_with(220)
        path.write_bytes(pixmap.tobytes("png"))

    dms = [{
        "dm_id": "dm-1",
        "tree": ir_mod.to_dict(IRNode(
            id="root",
            kind="section",
            children=[IRNode(
                id="picto",
                kind="figure",
                icn=pictogram.name,
                is_pictogram=True,
            )],
        )),
    }]
    monkeypatch.setattr(wizard_zip_export.ws, "load_dms", lambda _doc: dms)
    pictogram_names = wizard_zip_export.pictogram_image_names(
        SimpleNamespace(dms_json="[]")
    )

    exports, name_map = wizard_zip_export.prepare_zip_images(
        [illustration, pictogram],
        pictogram_names=pictogram_names,
        max_dimension=60,
        image_format="jpeg",
    )

    assert [item.archive_path for item in exports] == [
        "illustrations/figure-1.jpg",
        "pictograms/picto_chapitre_1.jpg",
    ]
    assert name_map == {
        "figure-1.png": "figure-1.jpg",
        "picto_chapitre_1.png": "picto_chapitre_1.jpg",
    }
    image = pymupdf.Pixmap(exports[0].content)
    assert max(image.width, image.height) == 60


def test_zip_xml_graphic_entity_uses_exported_extension(monkeypatch) -> None:
    dms = [{
        "dm_id": "dm-1",
        "dmc": "DMC-TEST-A-00-00-00-00A-040A-A",
        "dm_type": "descriptive",
        "tree": ir_mod.to_dict(IRNode(id="root", kind="section")),
    }]
    monkeypatch.setattr(wizard_zip_export.ws, "load_dms", lambda _doc: dms)
    monkeypatch.setattr(wizard_zip_export.wres, "dmrl_entries", lambda _doc: [])
    monkeypatch.setattr(wizard_zip_export, "build_reference_index", lambda _docs: {})
    xml = '<!ENTITY figure SYSTEM "figure-1.png" NDATA png>'

    result = wizard_zip_export.generate_zip_dm_xmls(
        SimpleNamespace(s1000d_issue="4.2"),
        ["dm-1"],
        db=object(),
        dm_xml_generator=lambda *_args, **_kwargs: xml,
        image_name_map={"figure-1.png": "figure-1.jpg"},
    )

    assert result["dm-1"] == '<!ENTITY figure SYSTEM "figure-1.jpg" NDATA jpg>'


def test_zip_images_convert_jpeg_to_png_with_matching_extension(tmp_path) -> None:
    source = tmp_path / "figure-2.jpg"
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 80, 40))
    pixmap.clear_with(220)
    source.write_bytes(pixmap.tobytes("jpeg"))

    exports, name_map = wizard_zip_export.prepare_zip_images(
        [source],
        pictogram_names=set(),
        max_dimension=None,
        image_format="png",
    )

    assert exports[0].archive_path == "illustrations/figure-2.png"
    assert exports[0].content.startswith(b"\x89PNG\r\n\x1a\n")
    assert name_map == {"figure-2.jpg": "figure-2.png"}
