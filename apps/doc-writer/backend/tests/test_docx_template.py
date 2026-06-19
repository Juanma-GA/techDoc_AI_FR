"""Moteur de template Word (`app.core.docx_template`) + dispatcher
(`app.core.template_format`).

Tests deterministes (pas de Mistral) : detection des zones regex/cadres,
remplissage en place avec preservation du style typographique, et selection du
moteur par format. La conversion PDF -> Word (pdf2docx) est testee si la lib est
installee (POC local-first : pas de CI, donc skip propre sinon).
"""

from __future__ import annotations

import io
import os
import tempfile

import pytest
from docx import Document
from docx.shared import Pt, RGBColor


def _build_template(path: str) -> None:
    """Template Word synthetique : marqueur {{cle}}, marqueur XXX style
    (gras/rouge/14pt), un paragraphe vide a remplir sous un titre, et une table
    label/valeur avec une cellule vide."""
    doc = Document()
    doc.add_paragraph("Rapport pour {{client}}")
    p = doc.add_paragraph("Reference : ")
    run = p.add_run("XXX")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
    doc.add_heading("Synthese", level=2)
    doc.add_paragraph("")  # cadre vide sous le titre "Synthese"
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Champ"
    table.cell(0, 1).text = "Valeur"
    table.cell(1, 0).text = "Date"
    table.cell(1, 1).text = ""  # cellule vide a remplir
    doc.save(path)


@pytest.fixture()
def template_path():
    d = tempfile.mkdtemp(prefix="docwriter_docx_")
    path = os.path.join(d, "template.docx")
    _build_template(path)
    yield path


def test_extract_zones_detects_placeholder_and_xxx(template_path) -> None:
    from app.core.docx_template import extract_zones

    zones = extract_zones(template_path)
    kinds = {z.kind for z in zones}
    assert "placeholder" in kinds
    assert "xxx" in kinds
    ph = next(z for z in zones if z.kind == "placeholder")
    assert ph.label == "{{ client }}"
    xxx = next(z for z in zones if z.kind == "xxx")
    # Label devine par le texte avant le marqueur dans le meme paragraphe.
    assert "Reference" in xxx.label
    # Ids sequentiels + target stable dp<N>.
    assert all(z.id.startswith("z_") for z in zones)
    assert all(z.target.startswith("dp") for z in zones)


def test_extract_all_frames_covers_empty_para_and_table_cells(template_path) -> None:
    from app.core.docx_template import extract_all_frames

    frames = extract_all_frames(template_path)
    labels = [f.label for f in frames]
    # Le paragraphe vide herite du titre precedent ("Synthese").
    assert "Synthese" in labels
    # La cellule vide (1,1) est listee, labellisee par ses voisins de table.
    assert any("Date" in lbl or "Valeur" in lbl for lbl in labels)
    assert all(f.kind == "frame" for f in frames)


def test_build_structure_has_no_bbox(template_path) -> None:
    from app.core.docx_template import build_structure

    struct = build_structure(template_path)
    assert struct["slide_width_emu"] == 0
    assert len(struct["slides"]) == 1
    shapes = struct["slides"][0]["shapes"]
    assert shapes  # au moins un cadre
    assert all(sh["bbox"] is None for sh in shapes)


def test_fill_zones_preserves_marker_run_style(template_path) -> None:
    from app.core.docx_template import extract_zones, fill_zones

    zones = extract_zones(template_path)
    mapping = {
        z.id: ("ACME Corp" if z.kind == "placeholder" else "REF-2026")
        for z in zones
    }
    blob = fill_zones(template_path, mapping)

    out = Document(io.BytesIO(blob))
    texts = [p.text for p in out.paragraphs]
    assert "Rapport pour ACME Corp" in texts
    # Le run du marqueur XXX -> REF-2026 conserve gras/couleur/taille.
    ref_para = next(p for p in out.paragraphs if "REF-2026" in p.text)
    styled = next(r for r in ref_para.runs if r.text == "REF-2026")
    assert styled.bold is True
    assert styled.font.size == Pt(14)
    assert styled.font.color.rgb == RGBColor(0xC0, 0x00, 0x00)
    # Le prefixe "Reference : " (run distinct, non style) reste intact.
    assert ref_para.text.startswith("Reference : REF-2026")


def test_fill_zones_fills_frames_and_table_cells(template_path) -> None:
    from app.core.docx_template import extract_all_frames, fill_zones

    frames = extract_all_frames(template_path)
    mapping = {f.id: f"<<{f.target}>>" for f in frames}
    blob = fill_zones(template_path, mapping, llm_zones=frames)

    out = Document(io.BytesIO(blob))
    # La cellule vide (1,1) est desormais remplie.
    last_cell = out.tables[0].rows[1].cells[1].text
    assert last_cell.startswith("<<")
    # Le paragraphe vide sous "Synthese" est rempli.
    assert any(p.text.startswith("<<") for p in out.paragraphs)


def test_fill_zones_multiline_uses_line_breaks(template_path) -> None:
    from app.core.docx_template import extract_zones, fill_zones

    zones = extract_zones(template_path)
    ph = next(z for z in zones if z.kind == "placeholder")
    blob = fill_zones(template_path, {ph.id: "Ligne1\nLigne2"})
    out = Document(io.BytesIO(blob))
    # python-docx joint les <w:br/> du meme run dans Paragraph.text sans '\n',
    # mais les deux fragments doivent etre presents.
    para = next(p for p in out.paragraphs if "Ligne1" in p.text)
    assert "Ligne2" in para.text


# ---------------------------------------------------------------------------
# Dispatcher de format.
# ---------------------------------------------------------------------------


def test_is_supported_template() -> None:
    from app.core.template_format import is_supported_template

    assert is_supported_template("a.pptx")
    assert is_supported_template("a.docx")
    assert is_supported_template("a.pdf")
    assert not is_supported_template("a.txt")
    assert not is_supported_template("a.xlsx")


def test_engine_for_docx(template_path) -> None:
    from app.core.template_format import resolve

    working, engine = resolve(template_path)
    assert engine.kind == "docx"
    assert engine.out_ext == "docx"
    assert working == template_path


def test_resolve_pdf_converts_to_docx() -> None:
    pytest.importorskip("pdf2docx")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    d = tempfile.mkdtemp(prefix="docwriter_pdf_")
    pdf = os.path.join(d, "tpl.pdf")
    c = canvas.Canvas(pdf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 760, "Rapport client {{client}}")
    c.drawString(72, 730, "Reference : XXX")
    c.save()

    from app.core.template_format import resolve

    working, engine = resolve(pdf)
    assert engine.kind == "docx"
    assert working.endswith(".converted.docx")
    assert os.path.exists(working)
    # Les marqueurs survivent a la conversion -> zones detectables.
    zones = engine.extract_zones(working)
    kinds = {z.kind for z in zones}
    assert "placeholder" in kinds or "xxx" in kinds
