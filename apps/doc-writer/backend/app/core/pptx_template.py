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
from pptx.enum.text import PP_ALIGN  # type: ignore[import-untyped]


PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_\-\.]+)\s*\}\}")
# 1 X ou plus (majuscule OU minuscule), isole par des limites de mot (ainsi
# "EXXON" ou "OXXXY" ne matchent pas car le X est colle a une lettre). Couvre
# les conventions "X", "XX", "XXX" (et plus), majuscule ou minuscule. Le seuil
# bas privilegie l'exhaustivite (lister tout, l'utilisateur elague via la
# corbeille) ; un "x" isole de multiplication peut etre un faux positif assume.
XXX_RE = re.compile(r"(?<![A-Za-z0-9])[Xx]+(?![A-Za-z0-9])")

_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

# Mapping consigne d'alignement (valeur string de l'API) -> enum python-pptx.
# "" (ou cle absente) = auto : on PRESERVE l'alignement d'origine du template
# au lieu d'en forcer un. Valeurs acceptees cote API : voir ALIGN_VALUES.
_ALIGN_TO_PP = {
    "left": PP_ALIGN.LEFT,
    "center": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT,
    "justify": PP_ALIGN.JUSTIFY,
}
ALIGN_VALUES = frozenset({"", "left", "center", "right", "justify"})


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
    active: bool = True  # False = zone exclue du remplissage a l'export
                         # (persistee dans le cache du Document). Detection
                         # != activation : l'utilisateur peut desactiver une
                         # zone sans la supprimer.
    instruction: str = ""  # Consignes libres de l'utilisateur pour cette zone,
                           # transmises au LLM de remplissage en plus du label
                           # (ex. "3 puces max", "ton commercial", "en anglais").
    align: str = ""        # Alignement horizontal FORCE du texte ecrit dans la
                           # zone : "left"|"center"|"right"|"justify". "" = auto
                           # (preserve l'alignement d'origine du template). Ne
                           # s'applique qu'aux zones target-based (llm/frame),
                           # pas aux marqueurs regex remplaces inline.


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
            # Id de shape au MEME format que build_structure (pptx_llm_analysis)
            # pour ancrer les zones regex a leur cadre (dedup avec le picker
            # d'ajout manuel + surlignage SVG). "" si la shape n'a pas d'id.
            shape_id = getattr(shape, "shape_id", None)
            base_target = f"s_{slide_idx}_{shape_id}" if shape_id is not None else ""

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
                        "shape_target": base_target,
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
                        cell_target = (
                            f"{base_target}_r{row_idx}_c{col_idx}"
                            if base_target
                            else ""
                        )
                        for para in cell.text_frame.paragraphs:
                            yield para, {
                                "slide_index": slide_idx,
                                "slide_title": title,
                                "location": f"Slide {slide_idx} / Tableau",
                                "prev_label": "",
                                "table_label": table_lbl,
                                "geo_label": geo_label,
                                "shape_target": cell_target,
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
                        target=ctx.get("shape_target", ""),
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
                        target=ctx.get("shape_target", ""),
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


def _qn(tag: str) -> str:
    """Nom qualifie Clark `{ns}tag` du namespace DrawingML (a:)."""
    return f"{{{_A_NS}}}{tag}"


def _as_rpr_xml(node) -> bytes:  # type: ignore[no-untyped-def]
    """Clone un node de proprietes de run (a:defRPr / a:endParaRPr) en le
    RENOMMANT en a:rPr : meme schema d'attributs (police/taille/couleur/bold),
    mais seul a:rPr est valide comme proprietes d'un run."""
    clone = etree.fromstring(etree.tostring(node))
    clone.tag = _qn("rPr")
    return etree.tostring(clone)


def _capture_style_rpr(tf, obj) -> bytes | None:  # type: ignore[no-untyped-def]
    """Style typographique (police/taille/couleur/bold) a cloner sur le contenu
    ecrit, EN CASCADE pour FORCER le respect du style du template meme quand la
    cible est VIDE (sinon retombee sur la police par defaut du master ->
    'polices/tailles non homogenes') :

      1. a:rPr du 1er run existant (cas nominal : cible deja stylee) ;
      2. a:pPr/a:defRPr du 1er paragraphe (proprietes de run par defaut) ;
      3. a:endParaRPr du 1er paragraphe (PowerPoint y stocke la police/taille
         voulue d'un paragraphe VIDE -> cas critique des cellules cibles vides) ;
      4. cellule de table : 1er a:rPr trouve dans la table parente (herite du
         style des cellules soeurs du tableau).

    Renvoie le XML (bytes) d'un node a:rPr clonable, ou None si rien trouve
    (on laisse alors le rendu hardcode au master, comportement historique).
    """
    rpr_path = f"{_qn('r')}/{_qn('rPr')}"
    for para in tf.paragraphs:
        p = para._p
        run_rpr = p.find(rpr_path)
        if run_rpr is not None:
            return etree.tostring(run_rpr)
        def_rpr = p.find(f"{_qn('pPr')}/{_qn('defRPr')}")
        if def_rpr is not None:
            return _as_rpr_xml(def_rpr)
        end_rpr = p.find(_qn("endParaRPr"))
        if end_rpr is not None:
            return _as_rpr_xml(end_rpr)
        break
    # Fallback cellule de table : style d'une cellule soeur du meme tableau.
    tc = getattr(obj, "_tc", None)
    if tc is not None:
        node = tc.getparent()
        tbl_tag = _qn("tbl")
        while node is not None and node.tag != tbl_tag:
            node = node.getparent()
        if node is not None:
            sib = node.find(f".//{rpr_path}")
            if sib is not None:
                return etree.tostring(sib)
    return None


def _write_text(obj, text: str, align: str = "") -> None:  # type: ignore[no-untyped-def]
    """Ecrit `text` dans le text_frame d'un Shape ou d'une Cell en FORCANT le
    style typographique du template (police, taille, couleur, bold) ET
    l'alignement horizontal du 1er paragraphe.

    Sans la restitution du rPr, `text_frame.text = ...` rebatit des runs sans
    rPr et le rendu retombe sur la police par defaut du master -> mosaique
    de polices/tailles d'une zone a l'autre ('police non homogene'). Le style
    est capture en cascade par `_capture_style_rpr` (run -> defRPr -> endParaRPr
    -> cellule soeur) pour couvrir les cibles VIDES qui n'ont aucun run.

    `tf.text = ...` reconstruit aussi les paragraphes et PERD leur `pPr` (donc
    l'alignement defini directement sur le paragraphe du template). On capture
    l'alignement d'origine avant reset pour le restituer.

    `align` (optionnel : "left"|"center"|"right"|"justify") FORCE un alignement
    et prime sur l'alignement d'origine. "" = auto (preserve l'origine).
    """
    if not hasattr(obj, "text_frame"):
        return
    tf = obj.text_frame

    # Alignement d'origine du 1er paragraphe (perdu par tf.text = ...).
    orig_align = None
    for para in tf.paragraphs:
        try:
            orig_align = para.alignment
        except (KeyError, ValueError):  # algn inconnu/non mappe -> auto
            orig_align = None
        break

    # Style a restituer (cascade anti-retombee master), clone XML pour
    # reappliquer apres reset (sinon le node serait deplace au lieu d'etre copie).
    first_rpr_xml = _capture_style_rpr(tf, obj)

    try:
        tf.text = text or ""
    except (AttributeError, ValueError):
        return

    # Alignement : la consigne explicite prime ; sinon on restitue l'origine
    # (None = on ne touche pas -> herite du placeholder/master comme avant).
    target_align = _ALIGN_TO_PP.get(align) if align else orig_align
    if target_align is not None:
        for para in tf.paragraphs:
            para.alignment = target_align

    if first_rpr_xml is None:
        return

    # Re-applique le style preserve sur tous les runs des paragraphes
    # nouvellement crees par tf.text = ... (un par ligne).
    for para in tf.paragraphs:
        for run in para.runs:
            existing_rpr = run._r.find(f"{{{_A_NS}}}rPr")
            if existing_rpr is not None:
                run._r.remove(existing_rpr)
            cloned_rpr = etree.fromstring(first_rpr_xml)
            run._r.insert(0, cloned_rpr)


def _is_static_label(text: str) -> bool:
    """Texte fixe traduisible : non vide, contient au moins une lettre, et SANS
    marqueur regex ({{cle}} / XXX) -> sinon c'est une zone geree par le fill."""
    if not text or not text.strip():
        return False
    if PLACEHOLDER_RE.search(text) or XXX_RE.search(text):
        return False
    return any(ch.isalpha() for ch in text)


def _collect_static_labels(prs, target_ids: set[str]):  # type: ignore[no-untyped-def]
    """Liste des (objet text_frame, texte) des libelles FIXES du template : tout
    text_box / cellule qui n'est PAS une cible de zone et ne porte pas de
    marqueur. Sert a la traduction des en-tetes/etiquettes vers la langue de
    sortie."""
    items: list = []
    for slide_idx, slide in enumerate(prs.slides, start=1):
        for shape in _iter_shapes_recursive(slide.shapes):
            sid = getattr(shape, "shape_id", None)
            if sid is None:
                continue
            base = f"s_{slide_idx}_{sid}"
            if shape.has_table:
                for r_idx, row in enumerate(shape.table.rows):
                    for c_idx, cell in enumerate(row.cells):
                        if f"{base}_r{r_idx}_c{c_idx}" in target_ids:
                            continue
                        txt = cell.text_frame.text
                        if _is_static_label(txt):
                            items.append((cell, txt))
            elif shape.has_text_frame:
                if base in target_ids:
                    continue
                txt = shape.text_frame.text
                if _is_static_label(txt):
                    items.append((shape, txt))
    return items


def fill_zones(
    path: str,
    mapping: dict[str, str],
    llm_zones: list[Zone] | None = None,
    *,
    erase_unmapped_regex: bool = False,
    translate=None,  # type: ignore[no-untyped-def]
) -> bytes:
    """Remplit le template :

    - Pass 1 : zones regex (xxx + placeholder) detectees par `_iter_paragraphs`.
      Compteur sequentiel partage avec `extract_zones` -> les ids `z_N` matchent.
    - Pass 2 (si `llm_zones` fourni) : zones LLM-detected, ecriture directe
      dans le shape ou la cellule pointee par `Zone.target`.
    - Pass 3 (si `translate` fourni) : traduit les libelles FIXES du template
      (en-tetes, etiquettes hors zones) vers la langue de sortie, pour un output
      100% dans la langue choisie. `translate(list[str]) -> list[str]`.

    Zone ids absents du mapping :
    - `erase_unmapped_regex=False` (defaut) : marqueurs laisses tels quels
      dans le pptx final.
    - `erase_unmapped_regex=True` : marqueurs remplaces par chaine vide. A
      utiliser quand l'appelant garantit que toutes les zones a conserver
      sont dans `mapping` (sinon on efface aussi les zones supprimees du
      cache par l'utilisateur -> coherent avec son intention).
    """
    prs = Presentation(path)

    # Pass 3 (collecte AVANT modifications) : on capture les libelles fixes
    # avant que les passes 1/2 ne touchent le document, puis on les traduit a la
    # fin. Les cibles de zones sont exclues (elles sont remplies, pas traduites).
    static_items = []
    if translate is not None:
        target_ids = {z.target for z in (llm_zones or []) if getattr(z, "target", "")}
        static_items = _collect_static_labels(prs, target_ids)

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
            elif erase_unmapped_regex:
                replacements[i] = ""
        if replacements:
            _apply_replacements_to_paragraph(para, full, matches, replacements)

    # Pass 2 : LLM zones (target-based). On loggue les targets non resolus
    # plutot que de skipper en silence (utile pour diagnostiquer un cache de
    # zones stale apres modif du template ou un id de target malforme).
    if llm_zones:
        import logging as _logging
        _log = _logging.getLogger("doc_writer.pptx_fill")
        for zone in llm_zones:
            if zone.id not in mapping:
                continue
            # Contenu vide : si la zone est ACTIVE, on l'ecrit quand meme ('')
            # pour VIDER la cible (l'utilisateur ne veut pas garder une zone
            # sans contenu trouve dans le resultat). Si la zone est inactive,
            # on preserve le contenu d'origine du template (contrat existant).
            if not mapping[zone.id] and not getattr(zone, "active", True):
                continue
            obj = _resolve_target(prs, zone.target)
            if obj is None:
                _log.warning(
                    "Zone LLM non ecrite : target %r introuvable dans le pptx "
                    "(label=%r). Cache stale ou template modifie ?",
                    zone.target, zone.label[:80],
                )
                continue
            _write_text(obj, mapping[zone.id], align=getattr(zone, "align", ""))

    # Pass 3 : traduction des libelles fixes (collectes avant les passes 1/2,
    # donc intacts). On preserve style + alignement (_write_text, align="").
    if translate is not None and static_items:
        originals = [txt for _obj, txt in static_items]
        try:
            translated = translate(originals)
        except Exception:  # noqa: BLE001
            translated = originals
        if isinstance(translated, list) and len(translated) == len(static_items):
            for (obj, orig), tr in zip(static_items, translated):
                if isinstance(tr, str) and tr.strip() and tr.strip() != orig.strip():
                    _write_text(obj, tr)

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
