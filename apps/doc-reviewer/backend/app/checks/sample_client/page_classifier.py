"""Sample page classifier for client bundle integration tests."""

from typing import Any

from app.parsers.pdf_parser import ParsedPdf


def classify_pages(parsed: ParsedPdf, _document: Any) -> None:
    for page in parsed.pages:
        page.page_type = "SAMPLE"