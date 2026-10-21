"""Align PDF pages by text while retaining explicit unmatched page slots."""

from __future__ import annotations

from difflib import SequenceMatcher

from app.core.document_comparison import PdfTextPage


def align_pages(
    reference_pages: tuple[PdfTextPage, ...],
    comparison_pages: tuple[PdfTextPage, ...],
    comparison_index: int,
) -> list[dict]:
    matcher = SequenceMatcher(
        a=[page.text for page in reference_pages],
        b=[page.text for page in comparison_pages],
    )
    alignment: list[dict] = []
    for operation, ref_start, ref_end, doc_start, doc_end in matcher.get_opcodes():
        if operation == "equal":
            for offset in range(ref_end - ref_start):
                reference_page = reference_pages[ref_start + offset].page
                comparison_page = comparison_pages[doc_start + offset].page
                alignment.append(
                    _row(
                        reference_page,
                        comparison_page,
                        "aligned",
                        f"reference-{reference_page}",
                        (reference_page, 0, 0, 0),
                    )
                )
        elif operation == "replace":
            paired_count = min(ref_end - ref_start, doc_end - doc_start)
            for offset in range(paired_count):
                reference_page = reference_pages[ref_start + offset].page
                comparison_page = comparison_pages[doc_start + offset].page
                alignment.append(
                    _row(
                        reference_page,
                        comparison_page,
                        "changed",
                        f"reference-{reference_page}",
                        (reference_page, 0, 0, 0),
                    )
                )
            for page in reference_pages[ref_start + paired_count : ref_end]:
                alignment.append(
                    _row(
                        page.page,
                        None,
                        "reference_only",
                        f"reference-{page.page}",
                        (page.page, 0, 0, 0),
                    )
                )
            anchor = ref_start + paired_count
            for offset, page in enumerate(comparison_pages[doc_start + paired_count : doc_end]):
                alignment.append(
                    _row(
                        None,
                        page.page,
                        "comparison_only",
                        f"comparison-{comparison_index}-page-{page.page}",
                        (anchor + 0.5, 1, comparison_index, offset),
                    )
                )
        elif operation == "delete":
            for page in reference_pages[ref_start:ref_end]:
                alignment.append(
                    _row(
                        page.page,
                        None,
                        "reference_only",
                        f"reference-{page.page}",
                        (page.page, 0, 0, 0),
                    )
                )
        elif operation == "insert":
            for offset, page in enumerate(comparison_pages[doc_start:doc_end]):
                alignment.append(
                    _row(
                        None,
                        page.page,
                        "comparison_only",
                        f"comparison-{comparison_index}-page-{page.page}",
                        (ref_start + 0.5, 1, comparison_index, offset),
                    )
                )
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
