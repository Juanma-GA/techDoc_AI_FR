"""Similarity-based, order-preserving alignment for PDF page sequences."""

from __future__ import annotations

from difflib import SequenceMatcher

from app.core.document_comparison import PdfTextPage

PAGE_SIMILARITY_THRESHOLD = 0.85
_MATCH = 0
_REFERENCE_ONLY = 1
_COMPARISON_ONLY = 2


def align_page_sequences(
    reference_pages: tuple[PdfTextPage, ...],
    comparison_pages: tuple[PdfTextPage, ...],
    page_similarity_threshold: float = PAGE_SIMILARITY_THRESHOLD,
) -> list[tuple[PdfTextPage | None, PdfTextPage | None]]:
    width = len(comparison_pages) + 1
    directions = bytearray((len(reference_pages) + 1) * width)
    for comparison_offset in range(1, width):
        directions[comparison_offset] = _COMPARISON_ONLY

    previous_scores = [0.0] * width
    for reference_offset, reference_page in enumerate(reference_pages, start=1):
        directions[reference_offset * width] = _REFERENCE_ONLY
        current_scores = [0.0] * width
        for comparison_offset, comparison_page in enumerate(comparison_pages, start=1):
            best_score = previous_scores[comparison_offset]
            direction = _REFERENCE_ONLY
            if current_scores[comparison_offset - 1] > best_score:
                best_score = current_scores[comparison_offset - 1]
                direction = _COMPARISON_ONLY

            similarity = _page_text_similarity(
                reference_page.text,
                comparison_page.text,
                page_similarity_threshold,
            )
            if similarity >= page_similarity_threshold:
                matched_score = previous_scores[comparison_offset - 1] + similarity
                if matched_score > best_score:
                    best_score = matched_score
                    direction = _MATCH

            current_scores[comparison_offset] = best_score
            directions[reference_offset * width + comparison_offset] = direction
        previous_scores = current_scores

    aligned_pages: list[tuple[PdfTextPage | None, PdfTextPage | None]] = []
    reference_offset = len(reference_pages)
    comparison_offset = len(comparison_pages)
    while reference_offset or comparison_offset:
        direction = directions[reference_offset * width + comparison_offset]
        if direction == _MATCH:
            aligned_pages.append(
                (reference_pages[reference_offset - 1], comparison_pages[comparison_offset - 1])
            )
            reference_offset -= 1
            comparison_offset -= 1
        elif direction == _REFERENCE_ONLY:
            aligned_pages.append((reference_pages[reference_offset - 1], None))
            reference_offset -= 1
        elif direction == _COMPARISON_ONLY:
            aligned_pages.append((None, comparison_pages[comparison_offset - 1]))
            comparison_offset -= 1
        else:
            raise RuntimeError("Invalid page alignment path.")

    aligned_pages.reverse()
    return aligned_pages


def _page_text_similarity(
    reference_text: str,
    comparison_text: str,
    page_similarity_threshold: float = PAGE_SIMILARITY_THRESHOLD,
) -> float:
    reference = reference_text.casefold()
    comparison = comparison_text.casefold()
    if not reference or not comparison:
        return 0.0
    if reference == comparison:
        return 1.0

    maximum_possible_ratio = 2 * min(len(reference), len(comparison)) / (
        len(reference) + len(comparison)
    )
    if maximum_possible_ratio < page_similarity_threshold:
        return 0.0

    matcher = SequenceMatcher(None, reference, comparison, autojunk=False)
    if matcher.quick_ratio() < page_similarity_threshold:
        return 0.0
    return matcher.ratio()
