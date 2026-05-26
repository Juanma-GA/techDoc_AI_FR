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

from app.core.mistral_client import MistralClient, MistralError
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


_SYSTEM_PROMPT = (
    "Tu analyses un template PowerPoint pour identifier les zones a remplir "
    "avec du contenu genere par un autre systeme.\n\n"
    "On te fournit un dump JSON du template : slides, shapes (text_box ou "
    "table avec rows et cells). Chaque shape/cellule a un `id` unique et un "
    "`text` qui contient son contenu actuel (souvent vide pour les zones a "
    "remplir, ou un libelle structurel pour les en-tetes).\n\n"
    "Pour chaque zone a remplir, retourne un objet :\n"
    "- id : 'z_1', 'z_2', ... (sequentiel a partir de 1)\n"
    "- target : l'id de la shape ou cellule (reutilise EXACTEMENT les ids "
    "fournis dans le dump)\n"
    "- label : description semantique courte (5-15 mots), ex. 'Nom de "
    "l'entreprise pour cette experience professionnelle'\n"
    "- kind : 'text_box' ou 'table_cell'\n\n"
    "REGLES STRICTES :\n"
    "1. INCLUS comme zones a remplir :\n"
    "   - Cellules de table vides positionnees a cote d'un libelle de "
    "structure (ex. cellule vide a cote d'une cellule 'Entreprise')\n"
    "   - Boites de texte vides ou contenant 'xxx', '...', '___'\n"
    "   - Boites de texte qui ressemblent a un champ a personnaliser (nom, "
    "titre de poste, date)\n"
    "2. EXCLUS de la liste :\n"
    "   - Les libelles structurels fixes du template ('Fonction', "
    "'Entreprise', 'Lieu', 'Annee', 'Contexte & objectifs', 'Projet / "
    "missions', 'Resultats', 'EXPERIENCES PROFESSIONNELLES', 'FORMATION', "
    "'COMPETENCES PRINCIPALES', 'OUTILS', 'LANGUES', 'HABILITATIONS', etc.)\n"
    "   - Les titres fixes ('Dossier Technique', logos, pieds de page)\n"
    "   - Les paginations, numeros de slide, mentions au lecteur\n"
    "   - Les shapes contenant deja 'xxx' (case-insensitive) ou '{{cle}}' "
    "(ces marqueurs sont detectes par un autre systeme deterministe, ne les "
    "double pas)\n\n"
    "Renvoie STRICTEMENT un objet JSON {'zones': [...]}. Pas d'explication, "
    "pas de markdown, pas de prose autour."
)


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


def split_zones(zones: list[Zone]) -> tuple[list[Zone], list[Zone]]:
    """Separe les zones regex (xxx + placeholder) des zones LLM (kind='llm').
    Utile pour `fill_zones(path, mapping, llm_zones=llm_part)`.
    """
    regex_zones = [z for z in zones if z.kind in ("xxx", "placeholder")]
    llm_zones = [z for z in zones if z.kind == "llm"]
    return regex_zones, llm_zones


def analyse_template(path: str, mistral: MistralClient) -> list[Zone]:
    """Appelle Mistral pour identifier les zones a remplir. Renvoie une liste
    de `Zone` avec `kind='llm'` et `target` pointant vers la shape ou cellule
    a remplir. En cas d'echec Mistral, leve `MistralError`."""
    dump = dump_template(path)
    location_by_target = _build_location_index(dump)

    if not dump.get("slides"):
        return []

    user_msg = (
        "Dump du template :\n```json\n"
        + json.dumps(dump, ensure_ascii=False)
        + "\n```\n\nRenvoie les zones a remplir."
    )

    raw = mistral.chat_json(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
    )
    zones_raw = raw.get("zones", [])
    if not isinstance(zones_raw, list):
        log.warning("LLM zones response is not a list: %r", type(zones_raw))
        return []

    out: list[Zone] = []
    seen_targets: set[str] = set()
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
    return out
