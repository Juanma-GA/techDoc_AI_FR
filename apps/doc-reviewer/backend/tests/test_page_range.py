"""Physical page-range validation and filtering."""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.core.page_range import filter_docx, filter_pdf, resolve_page_range
from app.parsers.docx_parser import Block, ParsedDocx
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def _parsed_pdf() -> ParsedPdf:
    pages = [ParsedPage(page=page, text=f"Page {page}") for page in range(1, 6)]
    return ParsedPdf(page_count=5, pages=pages, full_text="all", is_signed=False)


def test_page_range_defaults_to_last_document_page() -> None:
    assert resolve_page_range(2, None, 5) == (2, 5)


@pytest.mark.parametrize("first_page,last_page", [(3, 2), (1, 6), (6, None)])
def test_page_range_rejects_invalid_bounds(first_page: int, last_page: int | None) -> None:
    with pytest.raises(AppError) as raised:
        resolve_page_range(first_page, last_page, 5)
    assert raised.value.code == "PAGE_RANGE_INVALID"


def test_pdf_filter_preserves_physical_page_numbers() -> None:
    filtered = filter_pdf(_parsed_pdf(), 2, 4)

    assert filtered.page_count == 3
    assert [page.page for page in filtered.pages] == [2, 3, 4]
    assert "[PAGE: 1]" not in filtered.full_text
    assert "[PAGE: 4]" in filtered.full_text


def test_docx_filter_preserves_physical_page_numbers() -> None:
    blocks = [
        Block(target_id=f"dp{page}", index=page, zone="body", kind="paragraph", text=f"Page {page}", page=page)
        for page in range(1, 4)
    ]
    parsed = ParsedDocx(
        block_count=3,
        blocks=blocks,
        headers=["Header"],
        footers=["Footer"],
        full_text="all",
        zones={"body": blocks},
    )

    filtered = filter_docx(parsed, 2, 3)

    assert [block.page for block in filtered.blocks] == [2, 3]
    assert filtered.full_text == "Page 2\nPage 3"
    assert filtered.headers == []
    assert filtered.footers == []