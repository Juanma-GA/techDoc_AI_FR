"""Align PDF pages by text while retaining explicit unmatched page slots."""

from __future__ import annotations

from app.core.comparison_page_similarity import PAGE_SIMILARITY_THRESHOLD, align_page_sequences
from app.core.document_comparison import PdfTextPage


def align_pages(
    reference_pages: tuple[PdfTextPage, ...],
    comparison_pages: tuple[PdfTextPage, ...],
    comparison_index: int,
    page_similarity_threshold: float = PAGE_SIMILARITY_THRESHOLD,
) -> list[dict]:
    alignment: list[dict] = []
    reference_offset = 0
    comparison_offset = 0
    for reference_page, comparison_page in align_page_sequences(
        reference_pages,
        comparison_pages,
        page_similarity_threshold,
    ):
        if reference_page is not None and comparison_page is not None:
            status = "aligned" if reference_page.text == comparison_page.text else "changed"
            alignment.append(
                _row(
                    reference_page.page,
                    comparison_page.page,
                    status,
                    f"reference-{reference_page.page}",
                    (reference_page.page, 0, 0, 0),
                )
            )
            reference_offset += 1
            comparison_offset += 1
        elif reference_page is not None:
            alignment.append(
                _row(
                    reference_page.page,
                    None,
                    "reference_only",
                    f"reference-{reference_page.page}",
                    (reference_page.page, 0, 0, 0),
                )
            )
            reference_offset += 1
        elif comparison_page is not None:
            alignment.append(
                _row(
                    None,
                    comparison_page.page,
                    "comparison_only",
                    f"comparison-{comparison_index}-page-{comparison_page.page}",
                    (reference_offset + 0.5, 1, comparison_index, comparison_offset),
                )
            )
            comparison_offset += 1
        else:
            raise RuntimeError("Page alignment step contained no page.")
    return alignment


def _row(
    reference_page: int | None,
    comparison_page: int | None,
    status: str,
    slot_id: str,
    sort_key: tuple[float, int, int, int],
) -> dict:
    return {
        "slot_id": slot_id,
        "reference_page": reference_page,
        "comparison_page": comparison_page,
        "status": status,
        "_sort_key": sort_key,
    }


def combine_page_slots(comparisons: list[dict]) -> list[dict]:
    slots: dict[str, dict] = {}
    for comparison in comparisons:
        for row in comparison["page_alignment"]:
            slots.setdefault(
                row["slot_id"],
                {
                    "id": row["slot_id"],
                    "reference_page": row["reference_page"],
                    "_sort_key": row["_sort_key"],
                },
            )
    return [
        {"id": slot["id"], "reference_page": slot["reference_page"]}
        for slot in sorted(slots.values(), key=lambda item: item["_sort_key"])
    ]
