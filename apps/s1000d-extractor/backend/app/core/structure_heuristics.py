"""Detecteurs heuristiques de forme (signal *faible*, gratuit).

Ces fonctions identifient la FORME explicite d'un bloc (puce, numero, titre,
admonition, legende) sans jamais decider la balise S1000D finale - le choix de
balise depend du CONTEXTE, traite plus loin (`context_classifier` + `resolver`).

FR + EN car la doc legacy aero est bilingue.
"""

from __future__ import annotations

import re
import statistics

from app.core.ir import RawBlock

# --- Formes de liste ---------------------------------------------------------

_BULLET_RE = re.compile(r"^\s*[•·‣◦⁃∙\-–—*]\s+")  # noqa: RUF001 (puces en/em dash)
_ORDERED_RE = re.compile(r"^\s*(?:\(?\d{1,3}[.)]|\(?[a-z][.)]|\(?[ivxlcdm]{1,5}[.)])\s+", re.IGNORECASE)

# --- Admonitions S1000D (warning / caution / note) ---------------------------

_SEP = r"[\s:.\-]*"
_ADMONITION_RES: list[tuple[str, re.Pattern[str]]] = [
    ("warning", re.compile(r"^\s*(?:warning|avertissement|danger)\b" + _SEP, re.IGNORECASE)),
    ("caution", re.compile(r"^\s*(?:caution|attention|mise en garde)\b" + _SEP, re.IGNORECASE)),
    ("note", re.compile(r"^\s*(?:note|nota|remarque)\b" + _SEP, re.IGNORECASE)),
]

# --- Legende de figure -------------------------------------------------------

_CAPTION_RE = re.compile(r"^\s*(?:figure|fig\.?|illustration)\s*\d+", re.IGNORECASE)

# --- Titre numerote MULTI-niveau (1.2, 1.2.3 ...) ----------------------------
# Volontairement multi-niveau : un nombre seul suivi de "." (ex. "1. Deposer")
# est un item de liste ordonnee, pas un titre. Les titres de niveau 1 ("1
# Description") sont detectes par la taille de police, pas par ce regex.
_NUMBERED_HEADING_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2})+)\.?\s+\S")


def detect_list_kind(text: str) -> str | None:
    """Retourne "ordered" / "bullet" / None selon le marqueur de debut."""
    if _ORDERED_RE.match(text):
        return "ordered"
    if _BULLET_RE.match(text):
        return "bullet"
    return None


def strip_list_marker(text: str) -> str:
    """Retire le marqueur de liste en tete (puce ou numero) pour ne garder
    que le contenu de l'item."""
    text = _ORDERED_RE.sub("", text, count=1)
    text = _BULLET_RE.sub("", text, count=1)
    return text.strip()


def detect_admonition(text: str) -> str | None:
    """Retourne "warning" / "caution" / "note" si le bloc demarre par le
    mot-cle correspondant, sinon None."""
    for kind, pat in _ADMONITION_RES:
        if pat.match(text):
            return kind
    return None


def is_caption(text: str) -> bool:
    return bool(_CAPTION_RE.match(text))


def numbered_heading_depth(text: str) -> int | None:
    """Profondeur d'un titre numerote ("1.2.3" -> 3), sinon None."""
    m = _NUMBERED_HEADING_RE.match(text)
    if not m:
        return None
    return m.group(1).count(".") + 1


def body_font_size(blocks: list[RawBlock]) -> float:
    """Taille de police modale (corps de texte) du document.

    Sert de reference pour inferer les niveaux de titre cote PDF : un bloc
    nettement plus gros (ou gras) que le corps est un titre.
    """
    sizes = [round(b.font_size, 1) for b in blocks if b.font_size]
    if not sizes:
        return 0.0
    try:
        return statistics.mode(sizes)
    except statistics.StatisticsError:
        return statistics.median(sizes)


def infer_heading_level(block: RawBlock, body_size: float) -> int | None:
    """Niveau de titre infere d'un bloc PDF (None si ce n'est pas un titre).

    Combine trois signaux : titre numerote (prioritaire et fiable), taille de
    police > corps, et gras. La numerotation donne directement la profondeur.
    """
    depth = numbered_heading_depth(block.text)
    if depth is not None and len(block.text) < 200:
        return depth

    if body_size and block.font_size:
        ratio = block.font_size / body_size
        short = len(block.text) <= 120
        if ratio >= 1.4 and short:
            return 1
        if ratio >= 1.2 and short:
            return 2
        if (ratio >= 1.08 or block.bold) and short and not block.text.endswith("."):
            return 3
    return None


def to_table_rows(block: RawBlock) -> list[list[str]] | None:
    if block.is_table and block.table_rows:
        return block.table_rows
    return None
