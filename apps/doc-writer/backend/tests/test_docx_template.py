"""Moteur de template Word (`app.core.docx_template`) + dispatcher
(`app.core.template_format`).

Tests deterministes (pas de Mistral) : detection des zones regex/cadres,
remplissage en place avec preservation du style typographique, et selection du
moteur par format. La conversion PDF -> Word (pdf2docx) est testee si la lib est
installee (pdf2docx est optionnelle et le test est ignore si elle manque).
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
    doc.add_paragraph("Paragraphe de prose libre.")  # prose : cadre a part entiere
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


def test_extract_all_frames_is_exhaustive_includes_prose(template_path) -> None:
    """Aligne sur le PPTX : tout paragraphe (prose comprise) est un cadre, sauf
    ceux porteurs d'un marqueur regex (geres par extract_zones)."""
    from app.core.docx_template import extract_all_frames

    labels = [f.label for f in extract_all_frames(template_path)]
    # La prose libre est desormais listee comme cadre (label = son propre texte).
    assert "Paragraphe de prose libre." in labels
    # Les paragraphes a marqueur regex restent exclus (pas de double remplissage).
    assert not any("{{" in lbl or "XXX" in lbl for lbl in labels)


def test_extract_all_frames_prose_inactive_by_default(template_path) -> None:
    """Listing exhaustif mais defaut d'activation : prose non vide hors tableau
    = inactive ; paragraphes vides + cellules de tableau = actifs."""
    from app.core.docx_template import extract_all_frames

    frames = extract_all_frames(template_path)

    # Prose libre (paragraphe de texte non vide hors tableau) : listee mais
    # INACTIVE par defaut (ne pas reecrire le fixe).
    prose = next(f for f in frames if f.label == "Paragraphe de prose libre.")
    assert prose.active is False

    # Cellules de tableau : actives par defaut (emplacement plausible).
    table_cells = [f for f in frames if "Tableau" in f.location]
    assert table_cells and all(f.active for f in table_cells)

    # Le paragraphe VIDE sous "Synthese" (label herite = "Synthese", texte vide)
    # est actif ; le titre "Synthese" lui-meme (prose non vide) est inactif.
    synthese = [f for f in frames if f.label == "Synthese"]
    assert any(f.active for f in synthese)       # le paragraphe vide
    assert any(not f.active for f in synthese)   # le titre (prose)


def test_build_flow_orders_blocks_and_includes_markers(template_path) -> None:
    from app.core.docx_template import build_flow, extract_all_frames, extract_zones

    flow = build_flow(template_path)
    blocks = flow["blocks"]
    types = [b["type"] for b in blocks]
    # Paragraphes ET tableau presents, dans l'ordre de lecture (table apres prose).
    assert "paragraph" in types
    assert "table" in types
    assert types.index("paragraph") < types.index("table")

    # Le paragraphe a marqueur ({{client}} / XXX) est inclus (contrairement aux
    # frames) et signale has_marker=True.
    marker_blocks = [b for b in blocks if b["type"] != "table" and b["has_marker"]]
    assert marker_blocks
    assert any("{{" in b["text"] or "XXX" in b["text"] for b in marker_blocks)

    # La prose libre figure comme bloc paragraphe.
    assert any(b.get("text") == "Paragraphe de prose libre." for b in blocks)

    # Le tableau expose des lignes de cellules avec des ids dp<N>.
    table = next(b for b in blocks if b["type"] == "table")
    assert table["rows"] and table["rows"][0]
    assert all(cell["id"].startswith("dp") for row in table["rows"] for cell in row)

    # Les ids des blocs couvrent les cibles des zones (jointure front possible).
    flow_ids = {b["id"] for b in blocks}
    flow_ids |= {c["id"] for b in blocks for row in b.get("rows", []) for c in row}
    zone_targets = {
        z.target for z in (*extract_zones(template_path), *extract_all_frames(template_path))
    }
    assert zone_targets and zone_targets <= flow_ids


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


def test_fill_zones_empty_value_preserves_prose(template_path) -> None:
    """Une zone frame active dont le LLM ne renvoie RIEN (valeur vide) doit
    PRESERVER le texte d'origine du template (prose non detruite), pas l'effacer."""
    from app.core.docx_template import extract_all_frames, fill_zones

    frames = extract_all_frames(template_path)
    prose = next(f for f in frames if f.label == "Paragraphe de prose libre.")
    # Mapping : toutes les zones a "" (le LLM n'a rien trouve).
    mapping = {f.id: "" for f in frames}
    blob = fill_zones(template_path, mapping, llm_zones=frames)

    out = Document(io.BytesIO(blob))
    texts = [p.text for p in out.paragraphs]
    # La prose d'origine est intacte (non effacee par un remplissage vide).
    assert "Paragraphe de prose libre." in texts
    assert prose  # la zone existait bien


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
