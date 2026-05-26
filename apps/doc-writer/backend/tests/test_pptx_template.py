"""Tests unitaires pour app.core.pptx_template.

Couvre extract_zones + fill_zones : zones placeholder `{{cle}}`, zones libres
`XXX`, label devine par contexte (inline / paragraphe precedent / titre slide /
header de table), mix des deux types, multi-lignes.
"""

from __future__ import annotations

import io
import tempfile

import pytest
from pptx import Presentation  # type: ignore[import-untyped]
from pptx.util import Inches  # type: ignore[import-untyped]

from app.core.pptx_template import (
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
    """EXXON contient 'XX' mais on exige 3+ X isoles par limite de mot."""
    prs = Presentation()
    _slide_with_lines(prs, "T", ["EXXON Mobil", "XXX", "OXXXY"])
    path = _save(prs)

    zones = extract_zones(path)
    # Seul le 'XXX' isole doit etre detecte.
    assert len(zones) == 1


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
