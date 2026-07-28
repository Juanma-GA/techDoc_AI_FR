"""Tests pour app.core.pptx_llm_analysis.

Couvre :
- `dump_template` : structure JSON attendue (slides/shapes/tables)
- `split_zones` : separation regex vs LLM
- `analyse_template` : avec MistralClient mocke (pas d'appel reel)
- `fill_zones(llm_zones=...)` : remplissage par target_id (cellule + textbox)
"""

from __future__ import annotations

import io
import tempfile
from unittest.mock import MagicMock

from pptx import Presentation  # type: ignore[import-untyped]
from pptx.util import Inches  # type: ignore[import-untyped]

from app.core.pptx_llm_analysis import (
    analyse_template,
    dump_template,
    split_zones,
)
from app.core.pptx_template import Zone, fill_zones


def _save(prs) -> str:  # type: ignore[no-untyped-def]
    f = tempfile.NamedTemporaryFile(suffix=".pptx", delete=False)
    f.close()
    prs.save(f.name)
    return f.name


def test_dump_template_includes_text_boxes_and_tables():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Mon titre"
    tb = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    tb.text_frame.text = "Description : "
    tbl = slide.shapes.add_table(2, 2, Inches(1), Inches(4), Inches(6), Inches(1)).table
    tbl.cell(0, 0).text = "Header A"
    tbl.cell(0, 1).text = "Header B"
    tbl.cell(1, 0).text = "Donnee"
    tbl.cell(1, 1).text = ""

    path = _save(prs)
    dump = dump_template(path)

    assert "slides" in dump
    assert len(dump["slides"]) == 1
    s0 = dump["slides"][0]
    assert s0["title"] == "Mon titre"
    assert s0["index"] == 1
    # On doit voir au moins le textbox + le tableau (+ le titre comme shape).
    kinds = [sh["kind"] for sh in s0["shapes"]]
    assert "text_box" in kinds
    assert "table" in kinds


def test_dump_template_cells_have_ids():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    tbl = slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(4), Inches(2)).table
    tbl.cell(0, 0).text = "A"
    tbl.cell(1, 0).text = ""
    path = _save(prs)

    dump = dump_template(path)
    table_shape = next(sh for sh in dump["slides"][0]["shapes"] if sh["kind"] == "table")
    # Chaque cellule doit avoir un id qui inclut la position r/c.
    all_cell_ids = [c["id"] for row in table_shape["rows"] for c in row]
    assert all(cid.startswith("s_1_") and "_r" in cid and "_c" in cid for cid in all_cell_ids)


def test_split_zones_separates_kinds():
    zones = [
        Zone(id="z_1", kind="placeholder", slide_index=1, slide_title="", label="", location=""),
        Zone(id="z_2", kind="xxx", slide_index=1, slide_title="", label="", location=""),
        Zone(id="z_llm_1", kind="llm", slide_index=2, slide_title="", label="", location="", target="s_2_42"),
    ]
    regex_z, llm_z = split_zones(zones)
    assert len(regex_z) == 2
    assert len(llm_z) == 1
    assert llm_z[0].kind == "llm"


def test_analyse_template_skips_unknown_targets():
    """Si Mistral renvoie un target qui n'existe pas dans le dump, on le saute."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    tb = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    tb.text_frame.text = ""
    path = _save(prs)

    from app.db.session import SessionLocal

    fake_mistral = MagicMock()
    real_dump = dump_template(path)
    real_target = real_dump["slides"][0]["shapes"][0]["id"]
    # 2 zones : une avec target valide, une avec target fictif.
    fake_mistral.chat_json.return_value = {
        "zones": [
            {"id": "z_1", "target": real_target, "label": "Nom"},
            {"id": "z_2", "target": "s_99_999", "label": "Invalide"},
        ]
    }

    # `db` sert uniquement a lire le prompt systeme (get_prompt) : DB de test
    # vide -> fallback sur prompts.DEFAULTS['pptx_analysis'].
    db = SessionLocal()
    try:
        zones, dropped = analyse_template(path, fake_mistral, db)
    finally:
        db.close()
    assert len(zones) == 1
    assert dropped == 0
    assert zones[0].kind == "llm"
    assert zones[0].target == real_target


def test_fill_zones_writes_llm_target_text_box():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    tb = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    tb.text_frame.text = ""
    path = _save(prs)

    dump = dump_template(path)
    target_id = dump["slides"][0]["shapes"][0]["id"]
    llm_zone = Zone(
        id="z_llm_1",
        kind="llm",
        slide_index=1,
        slide_title="",
        label="Test",
        location="Slide 1",
        target=target_id,
    )
    out = fill_zones(path, {"z_llm_1": "Contenu rempli"}, llm_zones=[llm_zone])

    re_prs = Presentation(io.BytesIO(out))
    texts = [
        sh.text_frame.text
        for sh in re_prs.slides[0].shapes
        if sh.has_text_frame
    ]
    assert any("Contenu rempli" in t for t in texts)


def test_fill_zones_writes_llm_target_table_cell():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    tbl = slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(4), Inches(2)).table
    tbl.cell(0, 0).text = "Header"
    tbl.cell(1, 0).text = "Label"
    tbl.cell(1, 1).text = ""
    path = _save(prs)

    dump = dump_template(path)
    table_shape = next(sh for sh in dump["slides"][0]["shapes"] if sh["kind"] == "table")
    # Trouve l'id de la cellule (1,1)
    cell_id = next(
        c["id"]
        for row in table_shape["rows"]
        for c in row
        if c["id"].endswith("_r1_c1")
    )

    llm_zone = Zone(
        id="z_llm_1",
        kind="llm",
        slide_index=1,
        slide_title="",
        label="Valeur",
        location="Slide 1 / Tableau",
        target=cell_id,
    )
    out = fill_zones(path, {"z_llm_1": "42"}, llm_zones=[llm_zone])

    re_prs = Presentation(io.BytesIO(out))
    re_tbl = next(sh for sh in re_prs.slides[0].shapes if sh.has_table).table
    assert re_tbl.cell(1, 1).text_frame.text == "42"
