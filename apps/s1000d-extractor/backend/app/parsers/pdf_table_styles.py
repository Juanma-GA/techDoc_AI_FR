"""Cell-local title candidates recovered from PDF text spans."""

from __future__ import annotations

import re

import pymupdf as fitz

_BOLD_FLAG = 1 << 4
_MEDIUM_OR_BOLD_FONT = re.compile(r"(?:^|[-_])(?:md|bd)(?:it)?$")


def span_is_bold(span: dict) -> bool:
    font = str(span.get("font", "")).lower()
    flags = int(span.get("flags", 0))
    return bool(flags & _BOLD_FLAG) or "bold" in font or bool(_MEDIUM_OR_BOLD_FONT.search(font))


def _span_is_inside(span: dict, cell: list[float]) -> bool:
    bbox = span.get("bbox")
    if not bbox or len(bbox) != 4:
        return False
    center_x = (float(bbox[0]) + float(bbox[2])) / 2
    center_y = (float(bbox[1]) + float(bbox[3])) / 2
    return cell[0] <= center_x < cell[2] and cell[1] <= center_y < cell[3]


def _is_bold_uppercase_line(
    candidate: str, cell: list[float], lines: list[list[dict]],
) -> bool:
    if not candidate.isupper() or not any(character.isalpha() for character in candidate):
        return False
    expected = " ".join(candidate.split())
    for line in lines:
        visible = [
            span for span in line
            if _span_is_inside(span, cell) and str(span.get("text", "")).strip()
        ]
        line_text = " ".join("".join(str(span.get("text", "")) for span in visible).split())
        if visible and line_text == expected and all(span_is_bold(span) for span in visible):
            return True
    return False


def _cell_title(
    text: str, cell: list[float] | None, lines: list[list[dict]],
) -> str | None:
    cell_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if cell is None or len(cell_lines) < 2:
        return None

    title_lines: list[str] = []
    for candidate in cell_lines:
        if not _is_bold_uppercase_line(candidate, cell, lines):
            break
        title_lines.append(candidate)
    if not title_lines or len(title_lines) == len(cell_lines):
        return None
    return "\n".join(title_lines)


def extract_table_cell_titles(
    page: fitz.Page,
    rows: list[list[str]],
    cell_bboxes: list[list[list[float] | None]],
) -> list[list[str | None]]:
    text_lines: list[list[dict]] = []
    page_text = page.get_text("dict")
    if not isinstance(page_text, dict):
        raise TypeError("PyMuPDF returned an invalid dictionary for table text.")
    blocks = page_text.get("blocks", [])
    if not isinstance(blocks, list):
        raise TypeError("PyMuPDF returned invalid text blocks for table title detection.")
    for block in blocks:
        if not isinstance(block, dict):
            raise TypeError("PyMuPDF returned an invalid text block.")
        for line in block.get("lines", []):
            if not isinstance(line, dict):
                raise TypeError("PyMuPDF returned an invalid text line.")
            spans = line.get("spans", [])
            if not isinstance(spans, list):
                raise TypeError("PyMuPDF returned invalid text spans for a table cell.")
            text_spans = []
            for span in spans:
                if not isinstance(span, dict):
                    raise TypeError("PyMuPDF returned an invalid text span.")
                text_spans.append(span)
            text_lines.append(text_spans)
    return [
        [
            _cell_title(
                text,
                cell_bboxes[row_index][column]
                if row_index < len(cell_bboxes) and column < len(cell_bboxes[row_index])
                else None,
                text_lines,
            )
            for column, text in enumerate(row)
        ]
        for row_index, row in enumerate(rows)
    ]
