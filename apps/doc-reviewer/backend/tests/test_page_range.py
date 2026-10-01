"""Physical page-range validation and filtering."""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.core.page_range import (
    filter_docx,
    filter_pdf,
    filter_pdf_pages,
    resolve_page_range,
    select_pdf_page_numbers,
)
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


def test_pdf_filter_accepts_non_contiguous_physical_pages() -> None:
    filtered = filter_pdf_pages(_parsed_pdf(), [1, 4])

    assert filtered.page_count == 2
    assert [page.page for page in filtered.pages] == [1, 4]
    assert filtered.full_text == "[PAGE: 1]\nPage 1\n[PAGE: 4]\nPage 4"


def test_modified_page_selection_excludes_only_explicitly_unchanged_pages() -> None:
    parsed = _parsed_pdf()
    parsed.pages[0].is_modified = None
    parsed.pages[1].is_modified = True
    parsed.pages[2].is_modified = False
    parsed.pages[3].is_modified = True
    parsed.pages[4].is_modified = None

    assert select_pdf_page_numbers(
        parsed,
        first_page=1,
        last_page=None,
        modified_only=True,
    ) == [1, 2, 4, 5]


def test_page_override_selection_targets_exact_physical_page() -> None:
    assert select_pdf_page_numbers(
        _parsed_pdf(),
        first_page=1,
        last_page=None,
        modified_only=False,
        page_number=4,
    ) == [4]


def test_every_analysis_scope_excludes_explicitly_unchanged_pages() -> None:
    parsed = _parsed_pdf()
    for page, is_modified in zip(parsed.pages, [True, False, None, True, False]):
        page.is_modified = is_modified

    full_scope = select_pdf_page_numbers(
        parsed,
        first_page=1,
        last_page=None,
        modified_only=False,
    )
    modified_scope = select_pdf_page_numbers(
        parsed,
        first_page=1,
        last_page=None,
        modified_only=True,
    )
    range_scope = select_pdf_page_numbers(
        parsed,
        first_page=2,
        last_page=4,
        modified_only=False,
    )

    assert full_scope == [1, 3, 4]
    assert modified_scope == [1, 3, 4]
    assert range_scope == [3, 4]
    scoped = filter_pdf_pages(parsed, range_scope)
    assert all(page.is_modified is not False for page in scoped.pages)


def test_explicitly_unchanged_page_is_excluded_from_manual_rerun() -> None:
    parsed = _parsed_pdf()
    parsed.pages[3].is_modified = False

    assert select_pdf_page_numbers(
        parsed,
        first_page=1,
        last_page=None,
        modified_only=False,
        page_number=4,
    ) == []


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