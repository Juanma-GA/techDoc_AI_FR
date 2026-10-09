from app.checks.pagination_checks import run
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, PdfLine


def _document(*page_texts: str) -> ParsedPdf:
    pages = []
    for page_number, text in enumerate(page_texts, start=1):
        lines = [
            PdfLine(
                text=line,
                bbox=(36.0, 36.0 + index * 18.0, 500.0, 50.0 + index * 18.0),
                block_index=0,
                line_index=index,
            )
            for index, line in enumerate(text.splitlines())
            if line.strip()
        ]
        pages.append(
            ParsedPage(
                page=page_number,
                text=text,
                lines=lines,
                page_height=792.0,
            )
        )
    return ParsedPdf(
        page_count=len(pages),
        pages=pages,
        full_text="\n".join(page_texts),
        is_signed=False,
    )


def test_empty_and_labelled_blank_pages_count_toward_chapter_parity() -> None:
    for blank_page_text in ("", "BLANK"):
        parsed = _document(
            "CHAPTER 1: INTRODUCTION",
            "Chapter 1 content",
            "Chapter 1 continues",
            blank_page_text,
            "CHAPTER 2: SYSTEMS",
            "Chapter 2 content",
        )

        assert run(parsed) == []


def test_chapter_start_on_even_page_is_reported() -> None:
    parsed = _document(
        "Cover page",
        "CHAPTER 1: INTRODUCTION",
        "Chapter content",
        "End matter",
    )

    findings = run(parsed)

    assert len(findings) == 1
    assert findings[0].page == 2
    assert "page PDF 2 (paire)" in findings[0].message


def test_last_chapter_must_end_on_even_page() -> None:
    parsed = _document(
        "CHAPTER 1: INTRODUCTION",
        "Chapter content",
        "Final odd page",
    )

    findings = run(parsed)

    assert len(findings) == 1
    assert findings[0].page == 3
    assert "se termine à la page PDF 3 (impaire)" in findings[0].message


def test_page_scoped_analysis_uses_the_complete_document_for_parity() -> None:
    complete = _document(
        "CHAPTER 1: INTRODUCTION",
        "Chapter 1 content",
        "Chapter 1 continues",
        "CHAPTER 2: SYSTEMS",
        "Chapter 2 content",
        "End matter",
    )
    partial = ParsedPdf(
        page_count=complete.page_count,
        pages=[complete.pages[3]],
        full_text=complete.full_text,
        is_signed=False,
        full_document_pages=complete.pages,
    )

    findings = run(partial)

    assert len(findings) == 1
    assert findings[0].page == 4


def test_no_recognized_chapters_produces_no_findings() -> None:
    assert run(_document("Cover", "General document text", "End")) == []