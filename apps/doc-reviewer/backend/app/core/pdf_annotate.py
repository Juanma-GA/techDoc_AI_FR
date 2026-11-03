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
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from app.db.models import Suggestion


@dataclass(frozen=True)
class PreparationRepairRule:
    title: str
    instructions: tuple[str, ...]


@dataclass(frozen=True)
class MissingPageRepair:
    page_types: tuple[str, ...]
    rules: tuple[PreparationRepairRule, ...]


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


def build_commented_pdf(
    pdf_path: str | Path,
    suggestions: Iterable[Suggestion],
    preparation_repairs: Iterable[MissingPageRepair] = (),
) -> bytes:
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
        _append_preparation_repair_pages(doc, preparation_repairs)
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


def _append_preparation_repair_pages(
    doc: fitz.Document,
    repairs: Iterable[MissingPageRepair],
) -> None:
    width, height = fitz.paper_size("a4")
    margin = 48
    lines_per_page = 52
    for repair in repairs:
        body_lines: list[str] = []
        if not repair.rules:
            body_lines.append("Aucune règle active n'est associée à ce type de page.")
        for rule in repair.rules:
            body_lines.extend(_wrapped_lines(f"- {rule.title}", 88))
            if rule.instructions:
                for instruction in rule.instructions:
                    body_lines.extend(
                        _wrapped_lines(instruction, 88, initial_indent="  ", subsequent_indent="    ")
                    )
            else:
                body_lines.append("  Consigne détaillée non disponible.")

        chunks = [
            body_lines[index : index + lines_per_page]
            for index in range(0, len(body_lines), lines_per_page)
        ] or [[]]
        page_type_label = f"Type(s) déclaré(s) absent(s) : {' / '.join(repair.page_types)}"
        for page_number, chunk in enumerate(chunks, start=1):
            page = doc.new_page(width=width, height=height)
            page.insert_text(
                (margin, margin),
                "Annexe de préparation - pages à réparer",
                fontname="helv",
                fontsize=14,
            )
            heading_lines = _wrapped_lines(page_type_label, 88)
            if page_number > 1:
                heading_lines.append("(suite)")
            page.insert_textbox(
                fitz.Rect(margin, margin + 10, width - margin, margin + 52),
                "\n".join(heading_lines),
                fontname="helv",
                fontsize=10,
            )
            page.insert_textbox(
                fitz.Rect(margin, margin + 62, width - margin, height - margin),
                "\n".join(chunk),
                fontname="helv",
                fontsize=9,
                lineheight=1.2,
            )


def _wrapped_lines(
    value: str,
    width: int,
    *,
    initial_indent: str = "",
    subsequent_indent: str = "",
) -> list[str]:
    lines: list[str] = []
    for paragraph in value.splitlines() or [value]:
        wrapped = textwrap.wrap(
            paragraph,
            width=width,
            initial_indent=initial_indent,
            subsequent_indent=subsequent_indent,
        )
        lines.extend(wrapped or [initial_indent.rstrip()])
    return lines
