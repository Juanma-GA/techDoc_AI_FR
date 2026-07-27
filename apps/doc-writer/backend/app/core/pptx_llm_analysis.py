"""Analyse LLM-native d'un template PowerPoint.

Cas d'usage : templates avec un layout complexe (tables label/valeur cote-a-cote,
cellules fusionnees, headers irreguliers) ou les heuristiques regex de
`pptx_template.extract_zones` (xxx, {{cle}}) ne suffisent pas. On serialise le
template en JSON et on demande a Mistral d'identifier les zones a remplir.

Sortie : `list[Zone]` avec `kind="llm"` et `target` encodant le chemin precis
vers la shape ou la cellule (pour le remplissage ulterieur via `fill_zones`).

Pipeline complet :
1. `dump_template(path)` : python-pptx -> JSON structure (slides/shapes/tables)
2. `analyse_template(path, mistral)` : Mistral renvoie [{id, target, label, kind}]
3. Cache du resultat dans `Document.extracted_text` (cle "zones_v1")
4. `fill_zones(path, mapping, llm_zones=...)` : remplit en navigant par target

Le module est complementaire a `pptx_template.extract_zones` : on appelle les
deux, on concatene, et on remplit en une seule passe via `fill_zones`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pptx import Presentation  # type: ignore[import-untyped]

from sqlalchemy.orm import Session

from app.core.mistral_client import MistralClient
from app.core.prompts import get_prompt
from app.core.pptx_template import (
    Zone,
    _iter_shapes_recursive,
    _slide_title,
)


log = logging.getLogger("doc_writer.pptx_llm")


_MAX_TEXT_PER_SHAPE = 300
_MAX_CELLS_PER_TABLE = 80


def _shape_dump(shape, slide_idx: int) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    """Serialise une shape en dict (id, kind, contenu). Renvoie None si la
    shape n'expose pas de contenu textuel pertinent."""
    shape_id = getattr(shape, "shape_id", None)
    if shape_id is None:
        return None
    base_id = f"s_{slide_idx}_{shape_id}"

    if shape.has_table:
        rows_dump: list[list[dict[str, Any]]] = []
        cells_count = 0
        for r_idx, row in enumerate(shape.table.rows):
            row_data: list[dict[str, Any]] = []
            for c_idx, cell in enumerate(row.cells):
                if cells_count >= _MAX_CELLS_PER_TABLE:
                    break
                # Ignore les cellules "fantomes" de span.
                if getattr(cell, "is_spanned", False) and not getattr(
                    cell, "is_merge_origin", False
                ):
                    continue
                text = cell.text_frame.text.strip()[:_MAX_TEXT_PER_SHAPE]
                row_data.append(
                    {"id": f"{base_id}_r{r_idx}_c{c_idx}", "text": text}
                )
                cells_count += 1
            if row_data:
                rows_dump.append(row_data)
        return {"id": base_id, "kind": "table", "rows": rows_dump}

    if shape.has_text_frame:
        text = shape.text_frame.text.strip()[:_MAX_TEXT_PER_SHAPE]
        return {"id": base_id, "kind": "text_box", "text": text}

    return None


def dump_template(path: str) -> dict[str, Any]:
    """Renvoie une representation JSON-friendly du template, prete a etre
    envoyee a Mistral pour analyse."""
    prs = Presentation(path)
    slides: list[dict[str, Any]] = []
    for slide_idx, slide in enumerate(prs.slides, start=1):
        title = _slide_title(slide)
        shapes_dump: list[dict[str, Any]] = []
        for shape in _iter_shapes_recursive(slide.shapes):
            d = _shape_dump(shape, slide_idx)
            if d is not None:
                shapes_dump.append(d)
        slides.append({"index": slide_idx, "title": title, "shapes": shapes_dump})
    return {"slides": slides}


def _bbox_dict(shape) -> dict | None:  # type: ignore[no-untyped-def]
    """(left, top, width, height) en EMU, ou None si la shape n'a pas de
    position connue. Utilise par build_structure pour le rendu SVG."""
    try:
        if shape.top is None or shape.left is None:
            return None
        return {
            "left": int(shape.left),
            "top": int(shape.top),
            "width": int(shape.width or 0),
            "height": int(shape.height or 0),
        }
    except (AttributeError, TypeError):
        return None


# Defauts standard PowerPoint si les dimensions ne sont pas exposees
# (cas exceptionnels). 9144000 x 6858000 EMU = 10 x 7.5 pouces.
_DEFAULT_SLIDE_W_EMU = 9144000
_DEFAULT_SLIDE_H_EMU = 6858000


def _neighbour_label(grid: dict[tuple[int, int], str], r: int, c: int) -> str:
    """Label deterministe et STRICT d'une cellule cible (typiquement vide),
    deduit de son voisin STRUCTUREL IMMEDIAT. Remplace le nommage LLM (source
    d'hallucinations 'bon nom / mauvaise zone') par une lecture directe de la
    grille.

    Strictesse : on ne considere que le voisin PRESENT le plus proche dans
    chaque direction. Les cellules fantomes d'un merge (absentes de `grid`)
    sont transparentes -> on atterrit sur l'origine du merge. Mais si ce voisin
    immediat est VIDE, on n'insiste pas dans cette direction (pas de capture
    d'un libelle lointain appartenant a un autre groupe).

    Ordre : voisin gauche immediat (libelle de ligne), sinon voisin du dessus
    immediat (en-tete de colonne). Renvoie '' si aucun voisin immediat libelle
    -> la zone reste sans nom plutot que mal nommee.
    """
    left = ""
    for cc in range(c - 1, -1, -1):
        if (r, cc) in grid:
            left = grid[(r, cc)]  # 1er voisin gauche PRESENT (ghosts ignores)
            break
    if left:
        return left
    top = ""
    for rr in range(r - 1, -1, -1):
        if (rr, c) in grid:
            top = grid[(rr, c)]  # 1er voisin du dessus PRESENT
            break
    if top:
        return top
    return ""


def build_structure(path: str) -> dict[str, Any]:
    """Dump enrichi pour le rendu SVG du template : positions EMU + dimensions.

    Distinct de `dump_template` (utilise par le LLM pour l'analyse semantique)
    car le LLM n'a pas besoin des bbox et on veut limiter le token count cote
    prompt analyse.

    Structure des cellules de tables : on calcule la bbox de chaque cellule
    a partir de la position de la table + cumul des `column.width` et
    `row.height`. Les cellules fusionnees gardent leur bbox propre (la cellule
    'origine' du merge), les cellules 'spanned' fantomes sont ignorees.
    """
    prs = Presentation(path)
    slide_w = int(getattr(prs, "slide_width", None) or _DEFAULT_SLIDE_W_EMU)
    slide_h = int(getattr(prs, "slide_height", None) or _DEFAULT_SLIDE_H_EMU)

    slides: list[dict[str, Any]] = []
    for slide_idx, slide in enumerate(prs.slides, start=1):
        title = _slide_title(slide)
        loc_text = f"Slide {slide_idx}"
        loc_table = f"Slide {slide_idx} / Tableau"
        shapes_out: list[dict[str, Any]] = []

        for shape in _iter_shapes_recursive(slide.shapes):
            shape_id = getattr(shape, "shape_id", None)
            if shape_id is None:
                continue
            base_id = f"s_{slide_idx}_{shape_id}"
            bbox = _bbox_dict(shape)

            if shape.has_table:
                # Calcul des positions des cellules : on cumule les
                # column.width (x) et row.height (y) depuis le coin top-left
                # de la table. python-pptx expose `table.columns[i].width` et
                # `table.rows[i].height` en EMU.
                table = shape.table
                rows = list(table.rows)
                try:
                    col_widths = [int(c.width or 0) for c in table.columns]
                except Exception:  # noqa: BLE001
                    col_widths = []
                try:
                    row_heights = [int(r.height or 0) for r in rows]
                except Exception:  # noqa: BLE001
                    row_heights = []

                table_left = bbox["left"] if bbox else 0
                table_top = bbox["top"] if bbox else 0

                # 1er passage : grille (row, col) -> texte des cellules non
                # fantomes, pour deduire les labels voisins de facon
                # deterministe (cf. _neighbour_label).
                grid: dict[tuple[int, int], str] = {}
                for r_idx, row in enumerate(rows):
                    for c_idx, cell in enumerate(row.cells):
                        spanned = (
                            getattr(cell, "is_spanned", False)
                            and not getattr(cell, "is_merge_origin", False)
                        )
                        if spanned:
                            continue
                        grid[(r_idx, c_idx)] = (
                            cell.text_frame.text.strip()[:_MAX_TEXT_PER_SHAPE]
                        )

                y_cursor = table_top
                cells_count = 0
                for r_idx, row in enumerate(rows):
                    x_cursor = table_left
                    row_h = row_heights[r_idx] if r_idx < len(row_heights) else 0
                    for c_idx, cell in enumerate(row.cells):
                        if cells_count >= _MAX_CELLS_PER_TABLE:
                            break
                        col_w = col_widths[c_idx] if c_idx < len(col_widths) else 0
                        # Cellules fantomes d'un merge : on les skip mais on
                        # avance quand meme le curseur x pour ne pas decaler
                        # les colonnes suivantes.
                        spanned = (
                            getattr(cell, "is_spanned", False)
                            and not getattr(cell, "is_merge_origin", False)
                        )
                        if not spanned:
                            cell_text = grid.get((r_idx, c_idx), "")
                            # Label deterministe : texte propre si la cellule
                            # est deja libellee, sinon le voisin structurel
                            # (gauche puis haut). Plus de devinette LLM.
                            label = cell_text or _neighbour_label(
                                grid, r_idx, c_idx
                            )
                            shapes_out.append({
                                "id": f"{base_id}_r{r_idx}_c{c_idx}",
                                "kind": "table_cell",
                                "location": loc_table,
                                "text": cell_text,
                                "label": label,
                                "bbox": {
                                    "left": x_cursor,
                                    "top": y_cursor,
                                    "width": col_w,
                                    "height": row_h,
                                },
                            })
                            cells_count += 1
                        x_cursor += col_w
                    y_cursor += row_h
                continue

            if shape.has_text_frame:
                text = shape.text_frame.text.strip()[:_MAX_TEXT_PER_SHAPE]
                shapes_out.append({
                    "id": base_id,
                    "kind": "text_box",
                    "location": loc_text,
                    "text": text,
                    "label": text,
                    "bbox": bbox,
                })

        slides.append({
            "index": slide_idx,
            "title": title,
            "shapes": shapes_out,
        })

    return {
        "slide_width_emu": slide_w,
        "slide_height_emu": slide_h,
        "slides": slides,
    }


# Le prompt systeme est lu via `get_prompt(db, 'pptx_analysis')` (defaut dans
# `app.core.prompts.DEFAULTS['pptx_analysis']`). Editable depuis l'UI Parametres.


def _build_location_index(dump: dict[str, Any]) -> dict[str, tuple[int, str, str]]:
    """Map target_id -> (slide_index, slide_title, location_humaine)."""
    out: dict[str, tuple[int, str, str]] = {}
    for s in dump.get("slides", []):
        sidx = s.get("index", 0)
        title = s.get("title", "") or ""
        loc_text = f"Slide {sidx}"
        loc_table = f"Slide {sidx} / Tableau"
        for sh in s.get("shapes", []):
            sh_kind = sh.get("kind")
            if sh_kind == "text_box":
                out[sh["id"]] = (sidx, title, loc_text)
            elif sh_kind == "table":
                for row in sh.get("rows", []):
                    for cell in row:
                        out[cell["id"]] = (sidx, title, loc_table)
    return out


def _text_by_target(dump: dict[str, Any]) -> dict[str, str]:
    """Map target_id -> texte actuel de la shape ou cellule. Utilise pour les
    checks de coherence (filtrer les targets deja couverts par regex, detecter
    les targets a contenu substantiel = libelle structurel probable)."""
    out: dict[str, str] = {}
    for s in dump.get("slides", []):
        for sh in s.get("shapes", []):
            sh_kind = sh.get("kind")
            if sh_kind == "text_box":
                out[sh["id"]] = sh.get("text", "") or ""
            elif sh_kind == "table":
                for row in sh.get("rows", []):
                    for cell in row:
                        out[cell["id"]] = cell.get("text", "") or ""
    return out


def _is_regex_tainted(text: str) -> bool:
    """True si le texte contient deja un marqueur xxx ou {{cle}} -> il sera
    capture par extract_zones cote regex. Une zone LLM sur la meme target
    ecraserait l'ecriture regex (pass 1 puis pass 2 dans fill_zones)."""
    from app.core.pptx_template import PLACEHOLDER_RE, XXX_RE
    return bool(XXX_RE.search(text) or PLACEHOLDER_RE.search(text))


# Conventions reconnues comme placeholders (en + dans le prompt LLM aussi).
_PLACEHOLDER_LITERALS = frozenset({
    "...", "___",
    "a remplir", "votre contenu", "votre contenu ici", "votre texte ici",
    "tbd", "tba", "n/a",
    "to fill", "to do", "your content here", "your text here",
})


def _looks_like_placeholder(text: str) -> bool:
    """True si le texte est vide, regex-tainted, ou matche une convention
    placeholder. Strict : si False, le texte ressemble plutot a un libelle
    structurel ou a une vraie valeur metier -> probable mauvaise zone."""
    if not text:
        return True
    t = text.strip().lower()
    if not t:
        return True
    if _is_regex_tainted(text):
        return True
    if t in _PLACEHOLDER_LITERALS:
        return True
    return False


def extract_all_frames(path: str) -> list[Zone]:
    """Enumere TOUS les cadres du template en zones `kind="frame"`, actives par
    defaut. Objectif : lister tout par defaut (l'utilisateur elague ensuite),
    plutot que de ne lister que le sous-ensemble juge "a remplir".

    Reutilise `build_structure` : la liste produite couvre donc EXACTEMENT les
    memes cibles que le selecteur d'ajout manuel (coherence garantie entre la
    liste detectee et la liste des cibles disponibles).

    Exclus : les cibles dont le texte contient deja un marqueur regex
    (`xxx` / `{{cle}}`) -> elles sont gerees par `extract_zones` (remplissage
    sous-cadre) ; une zone target les ecraserait.
    """
    structure = build_structure(path)
    zones: list[Zone] = []
    counter = 0
    for s in structure.get("slides", []):
        sidx = int(s.get("index", 0))
        title = s.get("title", "") or ""
        for sh in s.get("shapes", []):
            target = sh.get("id", "") or ""
            if not target:
                continue
            text = (sh.get("text", "") or "").strip()
            if _is_regex_tainted(text):
                continue
            # Label deterministe calcule par build_structure : texte propre du
            # cadre si present, sinon voisin structurel immediat (cellule
            # libellee a gauche / au-dessus). PAS de repli sur le titre de
            # slide : une zone non identifiable reste sans nom ('' -> '—' cote
            # UI) plutot que mal nommee.
            label = (sh.get("label", "") or "").strip() or text
            counter += 1
            zones.append(
                Zone(
                    id=f"z_frame_{counter}",
                    kind="frame",
                    slide_index=sidx,
                    slide_title=title,
                    label=label[:200],
                    location=sh.get("location", "") or f"Slide {sidx}",
                    target=target,
                )
            )
    return zones


def split_zones(zones: list[Zone]) -> tuple[list[Zone], list[Zone]]:
    """Separe les zones regex (xxx + placeholder) des zones cible (kind='llm'
    ou 'frame'), ces dernieres etant remplies par target via `fill_zones`.
    Utile pour `fill_zones(path, mapping, llm_zones=llm_part)`.
    """
    regex_zones = [z for z in zones if z.kind in ("xxx", "placeholder")]
    target_zones = [z for z in zones if z.kind in ("llm", "frame")]
    return regex_zones, target_zones


def analyse_template(
    path: str,
    mistral: MistralClient,
    db: Session,
) -> tuple[list[Zone], int]:
    """Appelle Mistral pour identifier les zones a remplir. Renvoie
    `(zones_validees, dropped_count)`. `dropped_count` compte les zones que le
    LLM a proposees mais qu'on a filtrees pour cause de conflit (target deja
    couvert par un marqueur regex `xxx` / `{{cle}}` -> double-ecriture).
    En cas d'echec Mistral, leve `MistralError`.

    Le prompt systeme est lu via `get_prompt(db, 'pptx_analysis')` -> editable
    depuis l'UI Parametres. Defaut dans `prompts.DEFAULTS`.
    """
    dump = dump_template(path)
    location_by_target = _build_location_index(dump)
    text_by_target = _text_by_target(dump)

    if not dump.get("slides"):
        return [], 0

    system_prompt = get_prompt(db, "pptx_analysis")
    user_msg = (
        "Dump du template :\n```json\n"
        + json.dumps(dump, ensure_ascii=False)
        + "\n```\n\nRenvoie les zones a remplir."
    )

    raw = mistral.chat_json(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
    )
    zones_raw = raw.get("zones", [])
    if not isinstance(zones_raw, list):
        log.warning("LLM zones response is not a list: %r", type(zones_raw))
        return [], 0

    out: list[Zone] = []
    seen_targets: set[str] = set()
    dropped = 0
    counter = 0
    for entry in zones_raw:
        if not isinstance(entry, dict):
            continue
        target = entry.get("target", "")
        label = entry.get("label", "")
        if not isinstance(target, str) or not isinstance(label, str):
            continue
        if target not in location_by_target:
            log.debug("LLM proposed unknown target %r, skipping", target)
            continue
        if target in seen_targets:
            continue

        current_text = text_by_target.get(target, "")
        # Pas de rejet pour conflit : on garde TOUTES les zones proposees, meme
        # si la cible contient deja un marqueur xxx/{{cle}} ou un texte
        # substantiel. L'utilisateur elague lui-meme. Au remplissage, la passe
        # par cible (pass 2) ecrit le contenu final dans la shape ; un eventuel
        # marqueur regex y est ecrase proprement. On se contente de logguer les
        # cas potentiellement suspects (diagnostic), sans incrementer `dropped`.
        if current_text.strip() and not _looks_like_placeholder(current_text):
            log.warning(
                "LLM zone suspecte (target %r contient deja %r): label=%r",
                target, current_text[:60], label[:80],
            )

        seen_targets.add(target)
        slide_idx, slide_title, location = location_by_target[target]
        counter += 1
        out.append(
            Zone(
                id=f"z_llm_{counter}",
                kind="llm",
                slide_index=slide_idx,
                slide_title=slide_title,
                label=label[:200],
                location=location,
                target=target,
            )
        )
    return out, dropped
