"""Coverage for `locate_with_search_for` and bbox fallback semantics."""

from __future__ import annotations

import fitz

from app.parsers.pdf_parser import locate_with_search_for


def _build_pdf_with_two_occurrences(tmp_path) -> str:
    """One-page PDF with the word « MAINTENANCE » printed twice."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 80), "Section 1 — MAINTENANCE procedure", fontname="helv", fontsize=12)
    page.insert_text((50, 200), "Section 2 — MAINTENANCE complete", fontname="helv", fontsize=12)
    out = tmp_path / "multi.pdf"
    doc.save(str(out))
    doc.close()
    return str(out)


def test_locate_first_occurrence(tmp_path) -> None:
    path = _build_pdf_with_two_occurrences(tmp_path)
    doc = fitz.open(path)
    page = doc.load_page(0)
    rect = locate_with_search_for(page, "MAINTENANCE", span_index=0)
    doc.close()
    assert rect is not None
    x0, y0, x1, y1 = rect
    assert x1 > x0 and y1 > y0
    # First occurrence is the upper one in PDF top-left coordinates.
    assert y0 < 150


def test_locate_second_occurrence(tmp_path) -> None:
    path = _build_pdf_with_two_occurrences(tmp_path)
    doc = fitz.open(path)
    page = doc.load_page(0)
    rect = locate_with_search_for(page, "MAINTENANCE", span_index=1)
    doc.close()
    assert rect is not None
    _, y0, _, _ = rect
    # Second occurrence is in the lower section.
    assert y0 > 150


def test_locate_returns_none_when_text_absent(tmp_path) -> None:
    path = _build_pdf_with_two_occurrences(tmp_path)
    doc = fitz.open(path)
    page = doc.load_page(0)
    rect = locate_with_search_for(page, "non-existent-token", span_index=0)
    doc.close()
    assert rect is None


def test_locate_handles_empty_original(tmp_path) -> None:
    path = _build_pdf_with_two_occurrences(tmp_path)
    doc = fitz.open(path)
    page = doc.load_page(0)
    assert locate_with_search_for(page, "", span_index=0) is None
    doc.close()
