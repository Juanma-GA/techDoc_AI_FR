"""PyMuPDF annotations for text-layer comparison exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import fitz


def build_commented_pdf(
    pdf_path: Path,
    *,
    reference_filename: str,
    comparisons: list[dict[str, Any]],
    language: Literal["fr", "en"],
) -> bytes:
    labels = {
        "fr": {
            "reference": "Référence",
            "candidate": "Version",
            "page": "page",
            "difference": "Différence",
        },
        "en": {
            "reference": "Reference",
            "candidate": "Version",
            "page": "page",
            "difference": "Difference",
        },
    }[language]
    document = fitz.open(str(pdf_path))
    try:
        for comparison in comparisons:
            page_map = {
                row["comparison_page"]: row["reference_page"]
                for row in comparison["page_alignment"]
                if row["comparison_page"] is not None and row["reference_page"] is not None
            }
            groups: dict[str, list[dict[str, Any]]] = {}
            for change in comparison["changes"]:
                groups.setdefault(change["group_id"], []).append(change)
            for changes in groups.values():
                removed = [change for change in changes if change["kind"] == "removed"]
                added = [change for change in changes if change["kind"] == "added"]
                candidate_page = int((added or removed)[0]["page"])
                title = (
                    f"{labels['difference']} — {comparison['filename']} — "
                    f"{labels['page']} {candidate_page}"
                )
                content_lines = [
                    f"{labels['reference']} ({reference_filename}): "
                    f"{', '.join(str(change['text']) for change in removed) or '—'}",
                    f"{labels['candidate']} ({comparison['filename']}): "
                    f"{', '.join(str(change['text']) for change in added) or '—'}",
                ]
                content = "\n".join(content_lines)

                if removed:
                    for change in removed:
                        page_number = int(change["page"])
                        rect = _change_rect(change)
                        if rect is None or not 1 <= page_number <= document.page_count:
                            continue
                        page = document.load_page(page_number - 1)
                        annotation = page.add_highlight_annot(rect)
                        annotation.set_colors(stroke=(0.75, 0.2, 0.2))
                        annotation.set_info(title=title, content=content)
                        annotation.update()
                    continue

                change = added[0]
                reference_page_number = page_map.get(int(change["page"]))
                if reference_page_number is None:
                    reference_page_number = 1
                if not 1 <= reference_page_number <= document.page_count:
                    continue
                reference_page = document[reference_page_number - 1]
                rect = _change_rect(change)
                if rect is None:
                    point = fitz.Point(36, 36)
                else:
                    bbox = change["bbox"]
                    source_width = bbox.get("page_w") if isinstance(bbox, dict) else None
                    source_height = bbox.get("page_h") if isinstance(bbox, dict) else None
                    if (
                        isinstance(source_width, (int, float))
                        and source_width > 0
                        and isinstance(source_height, (int, float))
                        and source_height > 0
                    ):
                        point = fitz.Point(
                            rect.x0 * reference_page.rect.width / float(source_width),
                            rect.y0 * reference_page.rect.height / float(source_height),
                        )
                    else:
                        point = fitz.Point(rect.x0, rect.y0)
                    point.x = min(max(point.x, 18), reference_page.rect.width - 18)
                    point.y = min(max(point.y, 18), reference_page.rect.height - 18)
                annotation = reference_page.add_text_annot(point, content, icon="Comment")
                annotation.set_info(title=title, content=content)
                annotation.update()

        return document.tobytes(deflate=True, garbage=3)
    finally:
        document.close()


def _change_rect(change: dict[str, Any]) -> fitz.Rect | None:
    bbox = change["bbox"]
    if isinstance(bbox, dict):
        coordinates = tuple(bbox.get(key) for key in ("x0", "y0", "x1", "y1"))
    elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        coordinates = tuple(bbox)
    else:
        return None
    if any(not isinstance(value, (int, float)) for value in coordinates):
        return None
    rect = fitz.Rect(*(float(value) for value in coordinates))
    return None if rect.is_empty or rect.is_infinite else rect
