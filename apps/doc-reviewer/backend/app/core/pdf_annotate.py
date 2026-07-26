"""Export « PDF commente » : estampille les anomalies retenues comme annotations
PyMuPDF sur le PDF fidele, plus une page-sommaire.

C'est le livrable que le relecteur imprime/consulte pour corriger son document
Word (les redacteurs corrigent dans Word puis assemblent le PDF final a la main,
en s'appuyant sur ce PDF commente — cf. CR de reunion).

Chaque finding **non rejete** localise (bbox present) devient un surlignage +
une note (popup) numerotee portant `[n] [rule_code/severite] message` et la
suggestion. Les findings sans bbox (anomalies d'absence) apparaissent seulement
dans la page-sommaire finale.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF

from app.db.models import Suggestion

# Couleurs RGB (0..1) par severite pour le surlignage + la pastille.
_SEVERITY_COLOR: dict[str, tuple[float, float, float]] = {
    "error": (0.90, 0.20, 0.20),
    "warning": (0.95, 0.60, 0.10),
    "info": (0.25, 0.55, 0.95),
}


def _color(severity: str) -> tuple[float, float, float]:
    return _SEVERITY_COLOR.get((severity or "warning").lower(), _SEVERITY_COLOR["warning"])


def _rect_of(bbox: dict) -> fitz.Rect | None:
    x0, y0, x1, y1 = bbox.get("x0"), bbox.get("y0"), bbox.get("x1"), bbox.get("y1")
    if None in (x0, y0, x1, y1):
        return None
    try:
        rect = fitz.Rect(float(x0), float(y0), float(x1), float(y1))
    except (TypeError, ValueError):
        return None
    return rect if not rect.is_empty else None


def build_commented_pdf(pdf_path: str | Path, suggestions: Iterable[Suggestion]) -> bytes:
    """Retourne les octets d'un PDF annote a partir de `pdf_path` et des
    suggestions (deja filtrees sur « non rejetees » par l'appelant)."""
    doc = fitz.open(pdf_path)
    try:
        items = sorted(
            suggestions,
            key=lambda s: (s.page, _sort_y(s)),
        )
        summary: list[tuple[int, Suggestion, bool]] = []
        for n, sug in enumerate(items, start=1):
            try:
                bbox = json.loads(sug.bbox or "{}")
            except json.JSONDecodeError:
                bbox = {}
            rect = _rect_of(bbox) if isinstance(bbox, dict) else None
            page_index = max(0, min(sug.page - 1, doc.page_count - 1))
            located = rect is not None
            if located:
                page = doc.load_page(page_index)
                color = _color(sug.severity)
                annot = page.add_highlight_annot(rect)
                annot.set_colors(stroke=color)
                annot.set_info(
                    title=f"[{n}] {sug.rule_code} · {sug.severity}",
                    content=_note_body(sug),
                )
                annot.update()
            summary.append((n, sug, located))
        _append_summary_page(doc, summary)
        return doc.tobytes(deflate=True, garbage=3)
    finally:
        doc.close()


def _sort_y(sug: Suggestion) -> float:
    try:
        bbox = json.loads(sug.bbox or "{}")
        y = bbox.get("y0")
        return float(y) if y is not None else 1e9
    except (json.JSONDecodeError, TypeError, ValueError):
        return 1e9


def _note_body(sug: Suggestion) -> str:
    lines = [sug.message or ""]
    if sug.proposed_text and sug.proposed_text != sug.original_text:
        lines.append(f"Suggestion : {sug.proposed_text}")
    return "\n".join(l for l in lines if l)


def _append_summary_page(doc: fitz.Document, summary: list[tuple[int, "Suggestion", bool]]) -> None:
    """Ajoute une page-sommaire listant tous les findings (localises ou non)."""
    width, height = fitz.paper_size("a4")
    page = doc.new_page(width=width, height=height)
    margin = 48
    text = [f"PDF commente — {len(summary)} anomalie(s) retenue(s)", ""]
    for n, sug, located in summary:
        loc = f"p.{sug.page}" if located else "hors page (absence)"
        text.append(f"[{n}] ({sug.severity}) {sug.rule_code} — {loc}")
        if sug.message:
            text.append(f"    {sug.message}")
        if sug.proposed_text and sug.proposed_text != sug.original_text:
            text.append(f"    -> {sug.proposed_text}")
        text.append("")
    rect = fitz.Rect(margin, margin, width - margin, height - margin)
    page.insert_textbox(rect, "\n".join(text), fontname="helv", fontsize=9, align=0)
