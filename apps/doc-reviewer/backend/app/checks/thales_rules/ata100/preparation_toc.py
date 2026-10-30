from __future__ import annotations

import re

from app.checks.thales_rules.ata100.revision_engine import extract_footer
from app.parsers.pdf_parser import ParsedPdf


_TOC_MARKER = re.compile(
    r"(?i)\b(?:table\s+of\s+contents|contents|table\s+des\s+mati[eè]res|sommaire)\b"
)


def map_preparation_pages_to_toc(
    parsed: ParsedPdf,
    decisions: list[dict],
) -> None:
    contents_pages = [
        page
        for page in parsed.pages
        if _TOC_MARKER.search(page.text or "")
    ]
    for decision in decisions:
        if decision.get("is_modified") is not True:
            continue
        target_page = next(
            (page for page in parsed.pages if page.page == decision["page"]),
            None,
        )
        if target_page is None:
            continue
        footer = extract_footer(target_page)
        page_key = footer.page_key if footer is not None else None
        if not page_key or not contents_pages:
            decision.update(
                {"toc_page": None, "toc_bbox": None, "toc_entry": None}
            )
            continue
        page_number = page_key.split()[-1]
        pattern = re.compile(
            rf"(?<![\w]){re.escape(page_number)}\s*$",
            re.IGNORECASE,
        )
        matches = [
            (contents_page, line)
            for contents_page in contents_pages
            for line in contents_page.lines
            if pattern.search(" ".join(line.text.split()))
        ]
        if len(matches) != 1:
            decision.update(
                {"toc_page": None, "toc_bbox": None, "toc_entry": None}
            )
            continue
        toc_page, line = matches[0]
        decision.update(
            {
                "toc_page": toc_page.page,
                "toc_bbox": list(line.bbox),
                "toc_entry": line.text,
            }
        )
