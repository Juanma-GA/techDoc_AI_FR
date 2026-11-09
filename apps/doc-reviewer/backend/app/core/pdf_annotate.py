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
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from app.core.errors import AppError
from app.db.models import Suggestion


@dataclass(frozen=True)
class PreparationRepairRule:
    title: str
    instructions: tuple[str, ...]


@dataclass(frozen=True)
class MissingPageRepair:
    page_types: tuple[str, ...]
    rules: tuple[PreparationRepairRule, ...]


@dataclass(frozen=True)
class RevisionPlanSection:
    title: str
    lines: tuple[str, ...]


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
    revision_sections: Iterable[RevisionPlanSection] = (),
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
        for section in revision_sections:
            _append_text_pages(doc, section.title, section.lines)
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
    return "\n".join(line for line in lines if line)


def _append_summary_page(doc: fitz.Document, summary: list[tuple[int, Suggestion, bool]]) -> None:
    """Paginate the findings as well as the preparation plan."""
    text: list[str] = []
    for n, sug, located in summary:
        loc = f"p.{sug.page}" if located else f"p.{sug.page} - emplacement précis non localisé"
        text.append(f"[{n}] ({sug.severity}) {sug.rule_code} — {loc}")
        if sug.message:
            text.append(f"    {sug.message}")
        if sug.proposed_text and sug.proposed_text != sug.original_text:
            text.append(f"    -> {sug.proposed_text}")
        text.append("")
    _append_text_pages(doc, f"PDF commenté - {len(summary)} anomalie(s) retenue(s)", text)


def _append_preparation_repair_pages(
    doc: fitz.Document,
    repairs: Iterable[MissingPageRepair],
) -> None:
    for repair in repairs:
        body_lines = [
            f"Type(s) déclaré(s) absent(s) : {' / '.join(repair.page_types)}",
            "Page à créer dans le document source ; cette annexe n'est pas une page métier prête à insérer.",
            "",
        ]
        if not repair.rules:
            body_lines.append("Aucune règle active n'est associée à ce type de page.")
        for rule in repair.rules:
            body_lines.append(f"- {rule.title}")
            if rule.instructions:
                body_lines.extend(f"  {instruction}" for instruction in rule.instructions)
            else:
                body_lines.append("  Consigne détaillée non disponible.")

        _append_text_pages(
            doc,
            "Annexe de préparation - pages à réparer",
            body_lines,
            continuation=f"Type(s) absent(s) : {' / '.join(repair.page_types)}",
        )


def _wrap_pdf_lines(value: str, width: float, fontsize: float) -> list[str]:
    value = value.translate(str.maketrans({
        "\u2014": "-", "\u2013": "-", "\u2019": "'", "«": '"', "»": '"',
    }))
    font = fitz.Font(fontname="helv")
    lines: list[str] = []
    for paragraph in value.splitlines() or [value]:
        if not paragraph:
            lines.append("")
        while paragraph:
            low, high = 1, len(paragraph)
            while low < high:
                middle = (low + high + 1) // 2
                if font.text_length(paragraph[:middle], fontsize=fontsize) <= width:
                    low = middle
                else:
                    high = middle - 1
            end = low
            if end < len(paragraph):
                last_space = paragraph.rfind(" ", 0, end + 1)
                if last_space > len(paragraph) - len(paragraph.lstrip()):
                    end = last_space
            lines.append(paragraph[:end].rstrip())
            paragraph = paragraph[end:].lstrip()
    return lines


def _append_text_pages(
    doc: fitz.Document,
    title: str,
    values: Iterable[str],
    *,
    continuation: str = "",
) -> None:
    width, height = fitz.paper_size("a4")
    margin, fontsize, lineheight = 48, 9, 12
    content_width = width - 2 * margin
    title_lines = _wrap_pdf_lines(title, content_width, 13)
    continuation_lines = _wrap_pdf_lines(continuation, content_width, fontsize) if continuation else []
    body_top = margin + 18 * len(title_lines) + lineheight * len(continuation_lines) + 12
    lines_per_page = int((height - margin - body_top) // lineheight) - 1
    if lines_per_page < 1:
        raise AppError(
            "PDF_EXPORT_LAYOUT_ERROR", "Le titre du récapitulatif PDF dépasse une page.", status_code=500,
        )
    lines = [line for value in values for line in _wrap_pdf_lines(value, content_width, fontsize)]
    for start in range(0, max(1, len(lines)), lines_per_page):
        page = doc.new_page(width=width, height=height)
        page.insert_text((margin, margin), title_lines, fontname="helv", fontsize=13, lineheight=18 / 13)
        if continuation_lines:
            page.insert_text(
                (margin, margin + 18 * len(title_lines)),
                continuation_lines,
                fontname="helv",
                fontsize=fontsize,
                lineheight=lineheight / fontsize,
            )
        for offset, line in enumerate(lines[start : start + lines_per_page]):
            page.insert_text(
                (margin, body_top + offset * lineheight),
                line,
                fontname="helv",
                fontsize=fontsize,
            )
        page.insert_text(
            (margin, height - 24),
            f"{'Suite - ' if start else ''}Page PDF exportée {doc.page_count}",
            fontname="helv",
            fontsize=8,
        )
