"""Reconnaissance des zones semantiques d'un CMM (mise en page specifique).

Mappe chaque `Block` d'un `ParsedDocx` vers une **zone metier nommee** afin que
les regles `zone_field` / `section_required` controlent la bonne region au lieu
de scanner tout le document (un check « footer copyright » ne lit que le footer,
« champs Fiche suiveuse remplis » ne lit que cette table, etc.).

Heuristique : les en-tetes/pieds viennent du conteneur (header/footer) ; dans le
corps, on suit des **ancres** textuelles (titres normalises) — une region court
de son ancre jusqu'au prochain titre de section. Le dictionnaire d'ancres est
**parametrable** (`ANCHORS`) pour s'adapter a un gabarit client legerement
different, sans toucher au code.
"""

from __future__ import annotations

from app.parsers.docx_parser import Block, ParsedDocx


# Zone semantique -> sous-chaines (en MAJUSCULES) qui declenchent la region.
# Ordre = priorite de detection sur un meme titre.
ANCHORS: dict[str, list[str]] = {
    "highlights_table": ["HIGHLIGHTS", "RECORD OF REVISIONS", "RECORD OF REVISION"],
    "fiche_suiveuse": ["FICHE SUIVEUSE", "FOLLOW-UP SHEET", "FOLLOW UP SHEET", "FOLLOW-UP"],
    "lep": ["LIST OF EFFECTIVE PAGES", "EFFECTIVE PAGES", "L.E.P"],
    "title_page": ["TITLE PAGE", "PAGE DE TITRE"],
}


def _anchor_for(text: str) -> str | None:
    up = text.upper()
    for zone, needles in ANCHORS.items():
        for needle in needles:
            if needle in up:
                return zone
    return None


def _is_section_break(block: Block) -> bool:
    """Un titre de section (Heading 0/1) cloture la region precedente."""
    return block.kind == "heading" and (block.heading_level is None or block.heading_level <= 1)


def recognize_zones(parsed: ParsedDocx) -> ParsedDocx:
    """Renseigne `Block.semantic_zone` et construit `parsed.zones` (mutation in place)."""
    current = "body"
    for block in parsed.blocks:
        if block.zone in {"header", "footer"}:
            block.semantic_zone = block.zone
            continue

        anchor = _anchor_for(block.text) if block.text.strip() else None
        if anchor is not None:
            current = anchor
            block.semantic_zone = anchor
            continue

        # Un nouveau titre de section qui n'est pas une ancre remet en "body".
        if _is_section_break(block) and block.text.strip():
            current = "body"

        block.semantic_zone = current

    zones: dict[str, list[Block]] = {}
    for block in parsed.blocks:
        zones.setdefault(block.semantic_zone or "body", []).append(block)
    parsed.zones = zones
    parsed.meta["zone_summary"] = {k: len(v) for k, v in zones.items()}
    return parsed
