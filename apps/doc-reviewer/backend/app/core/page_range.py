"""Validate and apply a physical page range without renumbering evidence."""

from __future__ import annotations

from app.core.errors import AppError
from app.parsers.docx_parser import ParsedDocx
from app.parsers.pdf_parser import ParsedPdf


def resolve_page_range(
    first_page: int,
    last_page: int | None,
    total_pages: int,
) -> tuple[int, int]:
    resolved_last = total_pages if last_page is None else last_page
    if total_pages < 1 or first_page > resolved_last or resolved_last > total_pages:
        raise AppError(
            "PAGE_RANGE_INVALID",
            f"Plage de pages invalide : {first_page}-{resolved_last} pour {total_pages} pages",
            status_code=422,
        )
    return first_page, resolved_last


def filter_pdf(parsed: ParsedPdf, first_page: int, last_page: int) -> ParsedPdf:
    pages = [page for page in parsed.pages if first_page <= page.page <= last_page]
    return ParsedPdf(
        page_count=len(pages),
        pages=pages,
        full_text="\n".join(f"[PAGE: {page.page}]\n{page.text}" for page in pages),
        is_signed=parsed.is_signed,
    )


def filter_docx(parsed: ParsedDocx, first_page: int, last_page: int) -> ParsedDocx:
    blocks = [block for block in parsed.blocks if first_page <= block.page <= last_page]
    target_ids = {block.target_id for block in blocks}
    return ParsedDocx(
        block_count=len(blocks),
        blocks=blocks,
        headers=parsed.headers if first_page == 1 else [],
        footers=parsed.footers if first_page == 1 else [],
        full_text="\n".join(block.text for block in blocks if block.text),
        revisions=[revision for revision in parsed.revisions if revision.target_id in target_ids],
        zones={
            name: [block for block in zone_blocks if block.target_id in target_ids]
            for name, zone_blocks in parsed.zones.items()
        },
        meta=dict(parsed.meta),
    )