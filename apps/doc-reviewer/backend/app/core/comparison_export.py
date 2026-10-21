"""PyMuPDF annotations for text-layer comparison exports."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Literal

import fitz


def build_commented_pdf(
    pdf_path: Path,
    *,
    reference_filename: str,
    comparison: dict[str, Any],
    language: Literal["fr", "en"],
) -> bytes:
    labels = {
        "fr": {
            "title": "Comparaison de {candidate} avec {reference}",
            "add": "Ajout",
            "remove": "Suppression",
            "empty": "Aucune différence textuelle détectée.",
            "page": "page",
        },
        "en": {
            "title": "Comparison of {candidate} with {reference}",
            "add": "Added",
            "remove": "Removed",
            "empty": "No text differences detected.",
            "page": "page",
        },
    }[language]
    document = fitz.open(str(pdf_path))
    try:
        for change in comparison["changes"]:
            if change["kind"] != "added":
                continue
            page_number = int(change["page"])
            bbox = change["bbox"]
            if page_number < 1 or page_number > document.page_count or len(bbox) != 4:
                continue
            rect = fitz.Rect(*bbox)
            if rect.is_empty or rect.is_infinite:
                continue
            page = document.load_page(page_number - 1)
            annotation = page.add_highlight_annot(rect)
            annotation.set_colors(stroke=(0.12, 0.55, 0.28))
            annotation.set_info(
                title=f"{labels['add']} — {labels['page']} {page_number}",
                content=str(change["text"]),
            )
            annotation.update()

        _append_summary_page(
            document,
            comparison=comparison,
            reference_filename=reference_filename,
            labels=labels,
        )
        return document.tobytes(deflate=True, garbage=3)
    finally:
        document.close()


def _append_summary_page(
    document: fitz.Document,
    *,
    comparison: dict[str, Any],
    reference_filename: str,
    labels: dict[str, str],
) -> None:
    title = labels["title"].format(
        candidate=str(comparison["filename"]),
        reference=reference_filename,
    )
    summary_lines = [title, ""]
    if not comparison["changes"]:
        summary_lines.append(labels["empty"])
    else:
        for change in comparison["changes"]:
            kind = labels["add"] if change["kind"] == "added" else labels["remove"]
            prefix = f"{kind} — {labels['page']} {change['page']}: "
            wrapped = textwrap.wrap(str(change["text"]), width=105) or [""]
            summary_lines.append(prefix + wrapped[0])
            summary_lines.extend(f"    {line}" for line in wrapped[1:])

    width, height = fitz.paper_size("a4")
    margin = 48
    for start in range(0, len(summary_lines), 58):
        page = document.new_page(width=width, height=height)
        page.insert_textbox(
            fitz.Rect(margin, margin, width - margin, height - margin),
            "\n".join(summary_lines[start : start + 58]),
            fontname="helv",
            fontsize=8,
        )
