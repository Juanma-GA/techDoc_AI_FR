"""Remplissage de templates PowerPoint, deux mecaniques unifiees.

Deux types de "zones" sont detectes dans le `.pptx` :

- **placeholder** : marqueur explicite `{{cle}}` ; le label est le nom de la cle.
- **xxx** : marqueur libre `XXX` (au moins 3 X majuscules) sans nom ; le label
  est devine par le contexte (texte avant XXX dans le meme paragraphe, sinon
  paragraphe precedent dans le meme text_frame, sinon header de ligne/colonne
  pour une cellule de table, sinon titre de la slide).

API publique :

- `extract_zones(path) -> list[Zone]` : decouvre toutes les zones dans l'ordre
  de parcours du document. Chaque zone porte un `id` deterministe (`z_1`,
  `z_2`...) que `fill_zones` retrouve dans le meme ordre.
- `fill_zones(path, mapping) -> bytes` : remplace chaque zone par
  `mapping[zone_id]` en preservant le style du 1er run et en convertissant
  `\\n` en `<a:br/>`. Les zones absentes du mapping sont laissees telles
  quelles (`XXX` ou `{{cle}}`).

Le format binaire `.ppt` (Office 97-2003) n'est pas supporte (limitation de
python-pptx).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Iterator

from lxml import etree  # type: ignore[import-untyped]
from pptx import Presentation  # type: ignore[import-untyped]
from pptx.enum.shapes import MSO_SHAPE_TYPE  # type: ignore[import-untyped]


PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_\-\.]+)\s*\}\}")
# 3 X ou plus consecutifs (majuscule OU minuscule), isole par des limites de
# mot (ainsi "EXXON" ou "OXXXY" ne matchent pas). Case-insensitive intentionnel
# pour accepter les conventions "XXX", "xxx", "Xxx" couramment utilisees.
XXX_RE = re.compile(r"(?<![A-Za-z0-9])[Xx]{3,}(?![A-Za-z0-9])")

_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


@dataclass
class Zone:
    id: str
    kind: str           # "placeholder" | "xxx" | "llm"
    slide_index: int    # 1-based
    slide_title: str
    label: str          # contexte semantique pour le LLM
    location: str       # libelle humain pour l'UI ("Slide 1 / Notes")
    target: str = ""    # Pour kind="llm" : path encode "s_<slide>_<shape_id>"
                        # ou "s_<slide>_<shape_id>_r<row>_c<col>" pour cellule.


# ---------------------------------------------------------------------------
# Walker partage : extract et fill parcourent dans le MEME ordre, ce qui
# garantit que les ids `z_N` sont identiques entre les deux passes.
# ---------------------------------------------------------------------------


def _para_text(paragraph) -> str:  # type: ignore[no-untyped-def]
    return "".join(run.text for run in paragraph.runs)


def _tf_text(tf) -> str:  # type: ignore[no-untyped-def]
    return "\n".join(_para_text(p) for p in tf.paragraphs)


def _slide_title(slide) -> str:  # type: ignore[no-untyped-def]
    try:
        if slide.shapes.title is not None and slide.shapes.title.has_text_frame:
            return _tf_text(slide.shapes.title.text_frame).strip()
    except (AttributeError, KeyError):
        pass
    return ""


def _iter_shapes_recursive(shapes_container) -> Iterator[object]:  # type: ignore[no-untyped-def]
    """Yield toutes les shapes feuilles (descend recursivement dans les groupes)."""
    for shape in shapes_container:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_shapes_recursive(shape.shapes)
        else:
            yield shape


# Tolerance geometrique en EMU (English Metric Unit). 914400 EMU = 1 pouce.
_EMU_TOLERANCE = 100000  # ~0.11 cm


def _shape_bbox(shape) -> tuple[int, int, int, int] | None:  # type: ignore[no-untyped-def]
    """(top, left, right, bottom) en EMU, ou None si non positionnee."""
    try:
        if shape.top is None or shape.left is None:
            return None
        top = int(shape.top)
        left = int(shape.left)
        width = int(shape.width or 0)
        height = int(shape.height or 0)
        return (top, left, left + width, top + height)
    except (AttributeError, TypeError):
        return None


def _slide_label_candidates(slide) -> list[dict]:  # type: ignore[no-untyped-def]
    """Toutes les shapes textuelles utilisables comme label (excluant celles
    qui sont elles-memes des zones a remplir, ou contenant du texte placeholder
    par defaut de PowerPoint)."""
    candidates: list[dict] = []
    for shape in _iter_shapes_recursive(slide.shapes):
        bbox = _shape_bbox(shape)
        if bbox is None:
            continue
        if not shape.has_text_frame:
            continue
        text = shape.text_frame.text.strip()
        if not text:
            continue
        if XXX_RE.search(text) or PLACEHOLDER_RE.search(text):
            continue
        # Placeholder de mise en page PowerPoint (FR + EN).
        if "Cliquez pour" in text or "Click to add" in text:
            continue
        candidates.append({"bbox": bbox, "text": text})
    return candidates


def _nearest_label(
    zone_bbox: tuple[int, int, int, int],
    candidates: list[dict],
) -> str:
    """Choisit le label le plus proche : au-dessus, OU a gauche dans la
    meme bande verticale. Score = distance pondere (distance principale +
    50% de la distance orthogonale).
    """
    if not candidates:
        return ""
    z_top, z_left, z_right, z_bottom = zone_bbox
    z_cx = (z_left + z_right) / 2
    z_cy = (z_top + z_bottom) / 2
    z_height = max(1, z_bottom - z_top)

    scored: list[tuple[float, str]] = []
    for c in candidates:
        c_top, c_left, c_right, c_bottom = c["bbox"]
        c_cx = (c_left + c_right) / 2
        c_cy = (c_top + c_bottom) / 2

        is_above = c_bottom <= z_top + _EMU_TOLERANCE
        is_horizontal_band = abs(c_cy - z_cy) < z_height * 1.5
        is_left = c_right <= z_left + _EMU_TOLERANCE and is_horizontal_band

        if is_above:
            distance = (z_top - c_bottom) + abs(c_cx - z_cx) * 0.5
        elif is_left:
            distance = (z_left - c_right) + abs(c_cy - z_cy) * 0.5
        else:
            continue
        scored.append((max(0.0, distance), c["text"]))

    if not scored:
        return ""
    scored.sort(key=lambda t: t[0])
    return scored[0][1]


def _iter_paragraphs(prs) -> Iterator[tuple[object, dict]]:  # type: ignore[no-untyped-def]
    """Yield (paragraph, context) pour chaque paragraphe ou chercher des matches.

    `context` contient :
      - slide_index, slide_title
      - location : "Slide N", "Slide N / Tableau", "Slide N / Notes"
      - prev_label : texte du paragraphe non-vide precedent dans le meme tf
      - table_label : header de ligne/colonne pour une cellule de table
      - geo_label : label devine par proximite geometrique
    """
    for slide_idx, slide in enumerate(prs.slides, start=1):
        title = _slide_title(slide)
        label_candidates = _slide_label_candidates(slide)

        for shape in _iter_shapes_recursive(slide.shapes):
            shape_bbox = _shape_bbox(shape)
            geo_label = (
                _nearest_label(shape_bbox, label_candidates) if shape_bbox else ""
            )

            if shape.has_text_frame:
                prev_label = ""
                for para in shape.text_frame.paragraphs:
                    yield para, {
                        "slide_index": slide_idx,
                        "slide_title": title,
                        "location": f"Slide {slide_idx}",
                        "prev_label": prev_label,
                        "table_label": "",
                        "geo_label": geo_label,
                    }
                    text = _para_text(para).strip()
                    if text:
                        prev_label = text

            if shape.has_table:
                table = shape.table
                rows = list(table.rows)
                header_cells: list[str] = []
                if rows:
                    header_cells = [
                        _tf_text(c.text_frame).strip() for c in rows[0].cells
                    ]
                for row_idx, row in enumerate(rows):
                    first_cell_text = (
                        _tf_text(row.cells[0].text_frame).strip()
                        if row.cells
                        else ""
                    )
                    for col_idx, cell in enumerate(row.cells):
                        col_header = (
                            header_cells[col_idx]
                            if col_idx < len(header_cells) and row_idx > 0
                            else ""
                        )
                        own = _tf_text(cell.text_frame).strip()
                        parts = [
                            p
                            for p in (first_cell_text, col_header)
                            if p and p != own
                        ]
                        table_lbl = " / ".join(parts)
                        for para in cell.text_frame.paragraphs:
                            yield para, {
                                "slide_index": slide_idx,
                                "slide_title": title,
                                "location": f"Slide {slide_idx} / Tableau",
                                "prev_label": "",
                                "table_label": table_lbl,
                                "geo_label": geo_label,
                            }

        if slide.has_notes_slide:
            prev_label = ""
            for para in slide.notes_slide.notes_text_frame.paragraphs:
                yield para, {
                    "slide_index": slide_idx,
                    "slide_title": title,
                    "location": f"Slide {slide_idx} / Notes",
                    "prev_label": prev_label,
                    "table_label": "",
                    "geo_label": "",
                }
                text = _para_text(para).strip()
                if text:
                    prev_label = text


def _matches_in_paragraph(full_text: str) -> list[dict]:
    """Tous les matches XXX + {{cle}} dans le paragraphe, tries par position."""
    out: list[dict] = []
    for m in XXX_RE.finditer(full_text):
        out.append(
            {
                "start": m.start(),
                "end": m.end(),
                "kind": "xxx",
                "key": None,
            }
        )
    for m in PLACEHOLDER_RE.finditer(full_text):
        out.append(
            {
                "start": m.start(),
                "end": m.end(),
                "kind": "placeholder",
                "key": m.group(1),
            }
        )
    out.sort(key=lambda x: x["start"])
    return out


def _label_for_xxx(full_text: str, start: int, ctx: dict) -> str:
    """Devine le label semantique d'une zone XXX.

    Priorite : (1) texte avant XXX dans le meme paragraphe (debarasse de
    ":", "-", "."), (2) paragraphe precedent dans le meme text_frame,
    (3) header ligne/colonne d'une cellule de table, (4) shape voisine
    geometriquement (au-dessus ou a gauche dans la slide), (5) titre de
    la slide.
    """
    inline = full_text[:start].strip(" \t:;,-.—–")
    if inline:
        return inline
    if ctx.get("table_label"):
        return ctx["table_label"]
    if ctx.get("prev_label"):
        return ctx["prev_label"]
    if ctx.get("geo_label"):
        return ctx["geo_label"]
    return ctx.get("slide_title", "")


# ---------------------------------------------------------------------------
# extract_zones
# ---------------------------------------------------------------------------


def extract_zones(path: str) -> list[Zone]:
    """Detection deterministe des zones via marqueurs explicites :
    `{{cle}}` (placeholder nomme) et `xxx` (zone libre, label devine).

    Pour les templates dont les zones a remplir n'ont pas de marqueur,
    voir le module `pptx_llm_analysis` qui delegue la detection a Mistral.
    """
    prs = Presentation(path)
    zones: list[Zone] = []
    counter = 0
    for para, ctx in _iter_paragraphs(prs):
        full = _para_text(para)
        if not full:
            continue
        for match in _matches_in_paragraph(full):
            counter += 1
            zid = f"z_{counter}"
            if match["kind"] == "xxx":
                label = _label_for_xxx(full, match["start"], ctx)
                zones.append(
                    Zone(
                        id=zid,
                        kind="xxx",
                        slide_index=ctx["slide_index"],
                        slide_title=ctx["slide_title"],
                        label=label,
                        location=ctx["location"],
                    )
                )
            else:
                key = match["key"] or ""
                zones.append(
                    Zone(
                        id=zid,
                        kind="placeholder",
                        slide_index=ctx["slide_index"],
                        slide_title=ctx["slide_title"],
                        label=f"{{{{ {key} }}}}",
                        location=ctx["location"],
                    )
                )
    return zones


# ---------------------------------------------------------------------------
# fill_zones
# ---------------------------------------------------------------------------


def _apply_replacements_to_paragraph(
    paragraph,  # type: ignore[no-untyped-def]
    full_text: str,
    matches: list[dict],
    replacements: dict[int, str],
) -> None:
    """Re-ecrit le paragraphe en remplacant les ranges des matches dont
    l'index figure dans `replacements`. Preserve le style du 1er run.

    `replacements` est indexe par la position du match dans `matches`
    (donc 0, 1, 2... dans l'ordre des matches dans le paragraphe).
    """
    if not matches or not replacements:
        return
    parts: list[str] = []
    last_end = 0
    for i, m in enumerate(matches):
        parts.append(full_text[last_end:m["start"]])
        if i in replacements:
            parts.append(replacements[i])
        else:
            parts.append(full_text[m["start"]:m["end"]])
        last_end = m["end"]
    parts.append(full_text[last_end:])
    new_text = "".join(parts)

    runs = list(paragraph.runs)
    if not runs:
        # Pas de run a styler : on ecrit dans le text_frame parent.
        paragraph.text = new_text  # type: ignore[attr-defined]
        return

    first_run = runs[0]
    for run in runs[1:]:
        run.text = ""

    lines = new_text.split("\n")
    first_run.text = lines[0]
    if len(lines) == 1:
        return

    r_el = first_run._r
    parent = r_el.getparent()
    rpr = r_el.find(f"{{{_A_NS}}}rPr")
    insert_idx = list(parent).index(r_el) + 1
    for line in lines[1:]:
        br = etree.Element(f"{{{_A_NS}}}br")
        parent.insert(insert_idx, br)
        insert_idx += 1
        new_r = etree.Element(f"{{{_A_NS}}}r")
        if rpr is not None:
            new_r.append(etree.fromstring(etree.tostring(rpr)))
        t = etree.SubElement(new_r, f"{{{_A_NS}}}t")
        t.text = line
        parent.insert(insert_idx, new_r)
        insert_idx += 1


def _resolve_target(prs, target: str):  # type: ignore[no-untyped-def]
    """Parse un target id 's_<slide>_<shape_id>[_r<row>_c<col>]' et renvoie
    l'objet python-pptx correspondant (`Shape` ou `_Cell`), ou None.
    """
    if not target.startswith("s_"):
        return None
    parts = target.split("_")
    try:
        slide_idx = int(parts[1])
        shape_id = int(parts[2])
    except (IndexError, ValueError):
        return None
    if slide_idx < 1 or slide_idx > len(prs.slides):
        return None
    slide = prs.slides[slide_idx - 1]
    target_shape = None
    for sh in _iter_shapes_recursive(slide.shapes):
        if getattr(sh, "shape_id", None) == shape_id:
            target_shape = sh
            break
    if target_shape is None:
        return None
    if len(parts) >= 5 and parts[3].startswith("r") and parts[4].startswith("c"):
        try:
            row = int(parts[3][1:])
            col = int(parts[4][1:])
        except ValueError:
            return None
        if not target_shape.has_table:
            return None
        try:
            return target_shape.table.cell(row, col)
        except (IndexError, KeyError):
            return None
    return target_shape


def _write_text(obj, text: str) -> None:  # type: ignore[no-untyped-def]
    """Ecrit `text` dans le text_frame d'un Shape ou d'une Cell. Les sauts de
    ligne deviennent des paragraphes (limitation python-pptx pour ce chemin).
    Le style precedent est perdu (acceptable pour cellules vides / boites
    de texte placeholder)."""
    if not hasattr(obj, "text_frame"):
        return
    try:
        obj.text_frame.text = text
    except (AttributeError, ValueError):
        pass


def fill_zones(
    path: str,
    mapping: dict[str, str],
    llm_zones: list[Zone] | None = None,
) -> bytes:
    """Remplit le template :

    - Pass 1 : zones regex (xxx + placeholder) detectees par `_iter_paragraphs`.
      Compteur sequentiel partage avec `extract_zones` -> les ids `z_N` matchent.
    - Pass 2 (si `llm_zones` fourni) : zones LLM-detected, ecriture directe
      dans le shape ou la cellule pointee par `Zone.target`.

    Zone ids absents du mapping : laisses tels quels.
    """
    prs = Presentation(path)

    # Pass 1 : regex zones.
    counter = 0
    for para, _ctx in _iter_paragraphs(prs):
        full = _para_text(para)
        if not full:
            continue
        matches = _matches_in_paragraph(full)
        if not matches:
            continue
        replacements: dict[int, str] = {}
        for i, _m in enumerate(matches):
            counter += 1
            zid = f"z_{counter}"
            if zid in mapping:
                replacements[i] = mapping[zid]
        if replacements:
            _apply_replacements_to_paragraph(para, full, matches, replacements)

    # Pass 2 : LLM zones (target-based).
    if llm_zones:
        for zone in llm_zones:
            if zone.id not in mapping or not mapping[zone.id]:
                continue
            obj = _resolve_target(prs, zone.target)
            if obj is None:
                continue
            _write_text(obj, mapping[zone.id])

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Backward compat : conserver l'ancienne API basee sur les seuls {{cle}}.
# ---------------------------------------------------------------------------


def extract_placeholders(path: str) -> list[str]:
    """Liste des cles `{{cle}}` uniques, dans l'ordre d'apparition.

    Conservee pour compat ; preferer `extract_zones` qui couvre aussi les XXX.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for zone in extract_zones(path):
        if zone.kind != "placeholder":
            continue
        # zone.label vaut "{{ cle }}", on re-extrait la cle.
        m = PLACEHOLDER_RE.search(zone.label)
        if m:
            key = m.group(1)
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered


def fill_template(path: str, mapping: dict[str, str]) -> bytes:
    """Compat : remplit en mappant cle -> contenu (pour les `{{cle}}`).

    Convertit le mapping cle->contenu en mapping zone_id->contenu en parcourant
    les zones de type placeholder.
    """
    zones = extract_zones(path)
    zone_mapping: dict[str, str] = {}
    for zone in zones:
        if zone.kind != "placeholder":
            continue
        m = PLACEHOLDER_RE.search(zone.label)
        if m and m.group(1) in mapping:
            zone_mapping[zone.id] = mapping[m.group(1)]
    return fill_zones(path, zone_mapping)
