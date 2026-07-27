"""Tests unitaires pour app.core.pptx_template.

Couvre extract_zones + fill_zones : zones placeholder `{{cle}}`, zones libres
`XXX`, label devine par contexte (inline / paragraphe precedent / titre slide /
header de table), mix des deux types, multi-lignes.
"""

from __future__ import annotations

import io
import tempfile

from pptx import Presentation  # type: ignore[import-untyped]
from pptx.enum.text import PP_ALIGN  # type: ignore[import-untyped]
from pptx.util import Inches, Pt  # type: ignore[import-untyped]

from app.core.pptx_llm_analysis import extract_all_frames
from app.core.pptx_template import (
    Zone,
    extract_placeholders,
    extract_zones,
    fill_template,
    fill_zones,
)


def _save(prs) -> str:  # type: ignore[no-untyped-def]
    f = tempfile.NamedTemporaryFile(suffix=".pptx", delete=False)
    f.close()
    prs.save(f.name)
    return f.name


def _slide_with_lines(prs, title: str, lines: list[str]):  # type: ignore[no-untyped-def]
    slide = prs.slides.add_slide(prs.slide_layouts[5])  # title only
    if slide.shapes.title is not None:
        slide.shapes.title.text = title
    tb = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(3))
    tf = tb.text_frame
    tf.text = lines[0]
    for line in lines[1:]:
        tf.add_paragraph().text = line
    return slide


# ---------------------------------------------------------------------------
# Placeholder zones (compat)
# ---------------------------------------------------------------------------


def test_extract_placeholders_compat_returns_unique_keys():
    prs = Presentation()
    _slide_with_lines(prs, "{{titre}}", ["Intro : {{intro}}", "{{intro}} encore"])
    path = _save(prs)

    keys = extract_placeholders(path)
    assert keys == ["titre", "intro"]


def test_fill_template_compat_replaces_placeholders():
    prs = Presentation()
    _slide_with_lines(prs, "{{titre}}", ["Hello {{name}}"])
    path = _save(prs)

    out = fill_template(path, {"titre": "Mon titre", "name": "Monde"})
    re_prs = Presentation(io.BytesIO(out))
    texts = []
    for sh in re_prs.slides[0].shapes:
        if sh.has_text_frame:
            texts.append(sh.text_frame.text)
    assert any("Mon titre" in t for t in texts)
    assert any("Hello Monde" in t for t in texts)


# ---------------------------------------------------------------------------
# XXX zones : detection + label par contexte
# ---------------------------------------------------------------------------


def test_xxx_zone_label_from_inline_prefix():
    """Cas : 'Section A : XXX' -> label = 'Section A'."""
    prs = Presentation()
    _slide_with_lines(prs, "Slide title", ["Section A : XXX"])
    path = _save(prs)

    zones = extract_zones(path)
    assert len(zones) == 1
    assert zones[0].kind == "xxx"
    assert zones[0].label == "Section A"
    assert zones[0].slide_index == 1
    assert zones[0].slide_title == "Slide title"


def test_xxx_zone_label_from_previous_paragraph():
    """Cas : paragraphe XXX seul -> label = paragraphe precedent non vide."""
    prs = Presentation()
    _slide_with_lines(prs, "Doc", ["Contexte de l intervention", "XXX"])
    path = _save(prs)

    zones = extract_zones(path)
    assert len(zones) == 1
    assert zones[0].label == "Contexte de l intervention"


def test_xxx_zone_label_falls_back_to_slide_title():
    prs = Presentation()
    _slide_with_lines(prs, "Mon titre de slide", ["XXX"])
    path = _save(prs)

    zones = extract_zones(path)
    assert len(zones) == 1
    assert zones[0].label == "Mon titre de slide"


def test_xxx_does_not_match_substring_in_word():
    """Les X colles a une lettre ne matchent pas (limites de mot) : 'EXXON' et
    'OXXXY' sont ignores, seul le 'XXX' isole est detecte."""
    prs = Presentation()
    _slide_with_lines(prs, "T", ["EXXON Mobil", "XXX", "OXXXY"])
    path = _save(prs)

    zones = extract_zones(path)
    # Seul le 'XXX' isole doit etre detecte.
    assert len(zones) == 1


def test_short_x_markers_detected():
    """Seuil 1+ : 'X', 'XX', 'XXX' isoles sont tous detectes."""
    prs = Presentation()
    _slide_with_lines(prs, "T", ["Nom : X", "Ville : XX", "Date : XXX"])
    path = _save(prs)

    zones = extract_zones(path)
    assert len(zones) == 3
    assert all(z.kind == "xxx" for z in zones)
    assert {"Nom", "Ville", "Date"} <= {z.label for z in zones}


def test_x_markers_case_insensitive_and_word_boundary():
    """Minuscules detectees ('x', 'xx', 'Xx') ; un x colle dans un mot
    ('maximum') ne matche pas grace aux limites de mot."""
    prs = Presentation()
    _slide_with_lines(
        prs, "T", ["Nom : x", "Ville : xx", "Mixte : Xx", "Mot : maximum"]
    )
    path = _save(prs)

    zones = extract_zones(path)
    labels = {z.label for z in zones}
    assert {"Nom", "Ville", "Mixte"} <= labels
    # "maximum" ne doit PAS generer de zone (x interne au mot).
    assert not any("max" in (z.label or "").lower() for z in zones)
    assert all(z.kind == "xxx" for z in zones)


def test_mix_xxx_and_placeholder_in_same_template():
    prs = Presentation()
    _slide_with_lines(prs, "{{titre}}", ["Contexte", "XXX", "Conclusion : {{conclu}}"])
    path = _save(prs)

    zones = extract_zones(path)
    kinds = [(z.kind, z.label) for z in zones]
    # Ordre : titre (placeholder), XXX (label 'Contexte'), conclu (placeholder).
    assert any(k[0] == "placeholder" and "titre" in k[1] for k in kinds)
    assert any(k[0] == "xxx" and k[1] == "Contexte" for k in kinds)
    assert any(k[0] == "placeholder" and "conclu" in k[1] for k in kinds)


# ---------------------------------------------------------------------------
# fill_zones : remplacement + style preserve + multi-lignes
# ---------------------------------------------------------------------------


def test_fill_zones_replaces_xxx_using_zone_id():
    prs = Presentation()
    _slide_with_lines(prs, "T", ["Contexte : XXX", "Detail", "XXX"])
    path = _save(prs)

    zones = extract_zones(path)
    assert len(zones) == 2
    mapping = {zones[0].id: "Premier rempli", zones[1].id: "Second rempli"}
    out = fill_zones(path, mapping)

    re_prs = Presentation(io.BytesIO(out))
    bodies = "\n".join(
        sh.text_frame.text for sh in re_prs.slides[0].shapes if sh.has_text_frame
    )
    assert "Premier rempli" in bodies
    assert "Second rempli" in bodies
    assert "XXX" not in bodies


def test_fill_zones_leaves_missing_ids_untouched():
    prs = Presentation()
    _slide_with_lines(prs, "T", ["A : XXX", "B : XXX"])
    path = _save(prs)

    zones = extract_zones(path)
    out = fill_zones(path, {zones[0].id: "OK"})
    re_prs = Presentation(io.BytesIO(out))
    body = "\n".join(
        sh.text_frame.text for sh in re_prs.slides[0].shapes if sh.has_text_frame
    )
    assert "A : OK" in body
    # La 2e zone est laissee telle quelle.
    assert "B : XXX" in body


def test_lowercase_xxx_is_detected():
    """xxx minuscules doit etre detecte (convention frequente dans les templates)."""
    prs = Presentation()
    _slide_with_lines(prs, "T", ["Section : xxx", "Autre : Xxx"])
    path = _save(prs)

    zones = extract_zones(path)
    assert len(zones) == 2
    assert all(z.kind == "xxx" for z in zones)


def test_geo_label_uses_nearest_shape_above():
    """Cas : un text_box `xxx` orphelin recupere le label d'une autre shape
    geometriquement au-dessus de lui sur la meme slide (groupes inclus)."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    # Label en haut (top=Inches(1)).
    tb_label = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(0.5))
    tb_label.text_frame.text = "COMPETENCES"
    # Zone XXX en dessous (top=Inches(2)).
    tb_xxx = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    tb_xxx.text_frame.text = "xxx"
    # Autre label, mais beaucoup plus bas (top=Inches(5)) - ne devrait PAS gagner.
    tb_far = slide.shapes.add_textbox(Inches(1), Inches(5), Inches(4), Inches(0.5))
    tb_far.text_frame.text = "LANGUES"

    path = _save(prs)
    zones = extract_zones(path)
    assert len(zones) == 1
    assert zones[0].label == "COMPETENCES"


# ---------------------------------------------------------------------------
# extract_all_frames : enumeration exhaustive (tous les cadres visuels)
# ---------------------------------------------------------------------------


def test_extract_all_frames_lists_unmarked_frames_and_skips_markers():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])  # title only
    if slide.shapes.title is not None:
        slide.shapes.title.text = "Titre"
    tb_free = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    tb_free.text_frame.text = "Bloc libre sans marqueur"
    tb_marked = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(4), Inches(1))
    tb_marked.text_frame.text = "Avec marqueur : XXX"
    path = _save(prs)

    frames = extract_all_frames(path)
    labels = [z.label for z in frames]

    assert {z.kind for z in frames} == {"frame"}
    assert all(z.active for z in frames)  # actives par defaut
    assert all(z.target.startswith("s_1_") for z in frames)
    # Le bloc libre ET le titre (cadres visuels) sont listes -> l'utilisateur elague.
    assert "Bloc libre sans marqueur" in labels
    assert "Titre" in labels
    # Le cadre porteur d'un marqueur est exclu (gere par extract_zones).
    assert not any("XXX" in (lbl or "") for lbl in labels)


def test_extract_all_frames_includes_empty_text_box():
    """Un cadre vide (placeholder a remplir) doit etre liste, label devine."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    if slide.shapes.title is not None:
        slide.shapes.title.text = "COMPETENCES"
    tb_empty = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(4), Inches(1))
    tb_empty.text_frame.text = ""
    path = _save(prs)

    frames = extract_all_frames(path)
    # Le cadre vide est present (target cible) malgre l'absence de texte.
    empty = [z for z in frames if z.target.endswith(f"_{tb_empty.shape_id}")]
    assert len(empty) == 1
    assert empty[0].active is True


def test_extract_all_frames_empty_cell_label_from_left_neighbour():
    """Cellule vide a droite d'une cellule libellee -> label deterministe =
    texte du voisin gauche (plus de devinette LLM)."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    table = slide.shapes.add_table(
        2, 2, Inches(1), Inches(1), Inches(6), Inches(2)
    ).table
    table.cell(0, 0).text = "Chiffre d affaires"
    table.cell(0, 1).text = ""  # cellule a remplir
    table.cell(1, 0).text = "Effectif"
    table.cell(1, 1).text = ""
    path = _save(prs)

    frames = extract_all_frames(path)
    # La cellule vide _r0_c1 herite du libelle de _r0_c0.
    empty_r0c1 = next(z for z in frames if z.target.endswith("_r0_c1"))
    empty_r1c1 = next(z for z in frames if z.target.endswith("_r1_c1"))
    assert empty_r0c1.label == "Chiffre d affaires"
    assert empty_r1c1.label == "Effectif"
    # La cellule libellee garde son propre texte comme label.
    labelled = next(z for z in frames if z.target.endswith("_r0_c0"))
    assert labelled.label == "Chiffre d affaires"


def test_extract_all_frames_strict_no_distant_neighbour_label():
    """Strictesse : une 2e cellule vide consecutive ne capture PAS le libelle
    distant de la 1re colonne. Voisin immediat vide -> zone sans nom."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    table = slide.shapes.add_table(
        1, 3, Inches(1), Inches(1), Inches(6), Inches(1)
    ).table
    table.cell(0, 0).text = "Type"
    table.cell(0, 1).text = ""  # voisin immediat de c0 -> herite "Type"
    table.cell(0, 2).text = ""  # voisin immediat (c1) vide -> PAS "Type"
    path = _save(prs)

    frames = extract_all_frames(path)
    c1 = next(z for z in frames if z.target.endswith("_r0_c1"))
    c2 = next(z for z in frames if z.target.endswith("_r0_c2"))
    assert c1.label == "Type"
    assert c2.label == ""  # pas de capture du libelle lointain


def test_extract_all_frames_orphan_empty_has_no_borrowed_title():
    """Une boite vide sans voisin libelle ne doit PAS heriter du titre de
    slide : label vide ('—' cote UI) plutot que nom emprunte."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    if slide.shapes.title is not None:
        slide.shapes.title.text = "COMPETENCES"
    tb_empty = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(4), Inches(1))
    tb_empty.text_frame.text = ""
    path = _save(prs)

    frames = extract_all_frames(path)
    empty = next(z for z in frames if z.target.endswith(f"_{tb_empty.shape_id}"))
    assert empty.label == ""  # pas de "COMPETENCES" emprunte


def test_extract_all_frames_empty_cell_label_from_top_neighbour():
    """Pas de voisin gauche libelle -> on remonte la colonne (voisin du dessus)."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    table = slide.shapes.add_table(
        2, 1, Inches(1), Inches(1), Inches(4), Inches(2)
    ).table
    table.cell(0, 0).text = "Commentaires"
    table.cell(1, 0).text = ""  # a remplir, sous l'en-tete
    path = _save(prs)

    frames = extract_all_frames(path)
    empty = next(z for z in frames if z.target.endswith("_r1_c0"))
    assert empty.label == "Commentaires"


def test_fill_zones_multiline_value_creates_breaks():
    prs = Presentation()
    _slide_with_lines(prs, "T", ["Section : XXX"])
    path = _save(prs)

    zones = extract_zones(path)
    out = fill_zones(path, {zones[0].id: "ligne1\nligne2\nligne3"})
    re_prs = Presentation(io.BytesIO(out))
    body = "\n".join(
        sh.text_frame.text for sh in re_prs.slides[0].shapes if sh.has_text_frame
    )
    for line in ("ligne1", "ligne2", "ligne3"):
        assert line in body


# ---------------------------------------------------------------------------
# Alignement : preservation de l'origine (auto) + forcage par zone
# ---------------------------------------------------------------------------


def _frame_zone(
    slide_index: int, shape_id: int, align: str = "", active: bool = True
) -> Zone:
    return Zone(
        id="z_align",
        kind="frame",
        slide_index=slide_index,
        slide_title="",
        label="",
        location="",
        target=f"s_{slide_index}_{shape_id}",
        active=active,
        align=align,
    )


def test_fill_zones_preserves_template_alignment_by_default():
    """align="" (auto) : l'alignement defini sur le paragraphe du template doit
    SURVIVRE au remplissage (sinon `tf.text = ...` le perdait vers le defaut)."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    tb = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    tb.text_frame.text = "placeholder"
    tb.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    path = _save(prs)

    zone = _frame_zone(1, tb.shape_id, align="")
    out = fill_zones(path, {zone.id: "Nouveau contenu"}, llm_zones=[zone])

    re_prs = Presentation(io.BytesIO(out))
    re_tb = next(sh for sh in re_prs.slides[0].shapes if sh.has_text_frame)
    assert re_tb.text_frame.text == "Nouveau contenu"
    assert re_tb.text_frame.paragraphs[0].alignment == PP_ALIGN.CENTER


def test_fill_zones_forces_alignment_overriding_template():
    """align explicite : prime sur l'alignement d'origine du template."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    tb = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    tb.text_frame.text = "placeholder"
    tb.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    path = _save(prs)

    zone = _frame_zone(1, tb.shape_id, align="right")
    out = fill_zones(path, {zone.id: "Force a droite"}, llm_zones=[zone])

    re_prs = Presentation(io.BytesIO(out))
    re_tb = next(sh for sh in re_prs.slides[0].shapes if sh.has_text_frame)
    assert re_tb.text_frame.paragraphs[0].alignment == PP_ALIGN.RIGHT


# ---------------------------------------------------------------------------
# Zone sans contenu : vide la cible (active) / preserve (inactive)
# ---------------------------------------------------------------------------


def test_fill_zones_clears_active_target_when_value_empty():
    """Zone cible ACTIVE sans contenu trouve -> la cible est VIDEE (on ne
    garde pas le texte d'origine du template dans le resultat)."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    tb = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    tb.text_frame.text = "Placeholder a remplacer"
    path = _save(prs)

    zone = _frame_zone(1, tb.shape_id, active=True)
    out = fill_zones(path, {zone.id: ""}, llm_zones=[zone])

    re_prs = Presentation(io.BytesIO(out))
    re_tb = next(sh for sh in re_prs.slides[0].shapes if sh.has_text_frame)
    assert re_tb.text_frame.text == ""


def test_fill_zones_translates_static_labels_not_zone_content():
    """Pass 3 : les libelles FIXES (hors zones) sont traduits via le callback ;
    le contenu d'une zone cible n'est PAS retraduit."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    label = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(0.5))
    label.text_frame.text = "Competences"
    target = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    target.text_frame.text = ""
    path = _save(prs)

    zone = _frame_zone(1, target.shape_id, active=True)

    def fake_translate(texts):
        return [t.upper() + " [T]" for t in texts]

    out = fill_zones(
        path, {zone.id: "Python, SQL"}, llm_zones=[zone], translate=fake_translate
    )
    re_prs = Presentation(io.BytesIO(out))
    texts = [
        sh.text_frame.text for sh in re_prs.slides[0].shapes if sh.has_text_frame
    ]
    assert any("COMPETENCES [T]" in x for x in texts)  # libelle traduit
    assert any("Python, SQL" in x for x in texts)      # zone remplie
    assert not any("PYTHON, SQL [T]" in x for x in texts)  # zone NON retraduite


# ---------------------------------------------------------------------------
# Forcer le respect des polices/tailles du template sur les cibles VIDES
# ---------------------------------------------------------------------------


def _cell_frame_zone(
    slide_index: int, shape_id: int, row: int, col: int, active: bool = True
) -> Zone:
    return Zone(
        id="z_cell",
        kind="frame",
        slide_index=slide_index,
        slide_title="",
        label="",
        location="",
        target=f"s_{slide_index}_{shape_id}_r{row}_c{col}",
        active=active,
    )


def test_fill_zones_preserves_font_size_on_empty_cell_via_defrpr():
    """Cellule cible VIDE stylee au niveau paragraphe (defRPr) : la taille
    voulue est restituee sur le contenu ecrit -> pas de retombee sur la police
    du master ('forcer le respect des polices/tailles')."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    gf = slide.shapes.add_table(1, 2, Inches(1), Inches(1), Inches(6), Inches(1))
    shape_id = gf.shape_id
    table = gf.table
    table.cell(0, 0).text = "Langues"
    empty = table.cell(0, 1)
    empty.text_frame.text = ""  # cible vide
    empty.text_frame.paragraphs[0].font.size = Pt(18)  # style sur paragraphe vide
    path = _save(prs)

    zone = _cell_frame_zone(1, shape_id, 0, 1)
    out = fill_zones(
        path, {zone.id: "Francais (langue maternelle)"}, llm_zones=[zone]
    )

    re_prs = Presentation(io.BytesIO(out))
    re_table = next(sh for sh in re_prs.slides[0].shapes if sh.has_table).table
    run = re_table.cell(0, 1).text_frame.paragraphs[0].runs[0]
    assert run.text == "Francais (langue maternelle)"
    assert run.font.size == Pt(18)


def test_fill_zones_inherits_font_from_sibling_cell():
    """Cellule cible vide SANS style propre -> herite du style d'une cellule
    soeur du tableau (fallback table), pas de la police du master."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    gf = slide.shapes.add_table(1, 2, Inches(1), Inches(1), Inches(6), Inches(1))
    shape_id = gf.shape_id
    table = gf.table
    sib = table.cell(0, 0)
    sib.text = "Effectif"
    sib.text_frame.paragraphs[0].runs[0].font.size = Pt(22)  # style soeur
    empty = table.cell(0, 1)
    empty.text_frame.text = ""  # vide, sans style propre
    path = _save(prs)

    zone = _cell_frame_zone(1, shape_id, 0, 1)
    out = fill_zones(path, {zone.id: "1200"}, llm_zones=[zone])

    re_prs = Presentation(io.BytesIO(out))
    re_table = next(sh for sh in re_prs.slides[0].shapes if sh.has_table).table
    run = re_table.cell(0, 1).text_frame.paragraphs[0].runs[0]
    assert run.font.size == Pt(22)


def test_fill_zones_keeps_inactive_target_when_value_empty():
    """Zone cible INACTIVE sans contenu -> contenu d'origine PRESERVE."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    tb = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    tb.text_frame.text = "Contenu d origine"
    path = _save(prs)

    zone = _frame_zone(1, tb.shape_id, active=False)
    out = fill_zones(path, {zone.id: ""}, llm_zones=[zone])

    re_prs = Presentation(io.BytesIO(out))
    re_tb = next(sh for sh in re_prs.slides[0].shapes if sh.has_text_frame)
    assert re_tb.text_frame.text == "Contenu d origine"
