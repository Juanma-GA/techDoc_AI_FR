from __future__ import annotations

from types import SimpleNamespace

from app.checks.thales_rules.ata100 import operations
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, Span


_THALES_ADDRESS = (
    "THALES AVS FRANCE SAS\n"
    "75\u201377 AV MARCEL DASSAULT\n"
    "CAMPUS THALES BORDEAUX\n"
    "33700 MERIGNAC\n"
    "FRANCE"
)


def _span(
    page: int,
    text: str,
    x: float,
    y: float,
    *,
    width: float = 70.0,
    font: str = "Arial",
) -> Span:
    return Span(
        text=text,
        bbox=(x, y, x + width, y + 8.0),
        page=page,
        font=font,
        size=10.0,
    )


def _vendor_page(
    page_number: int,
    rows: list[tuple[str, str, str, str]],
    *,
    title: bool = False,
    headers: bool = True,
) -> ParsedPage:
    spans: list[Span] = []
    if title:
        spans.append(
            _span(
                page_number,
                "VENDOR CODE LIST",
                20.0,
                15.0,
                width=150.0,
                font="Arial-Bold",
            )
        )
    if headers:
        spans.extend(
            [
                _span(page_number, "CODE", 20.0, 40.0, width=30.0),
                _span(page_number, "VENDOR'S ADDRESS", 90.0, 40.0, width=110.0),
                _span(page_number, "CODE", 300.0, 40.0, width=30.0),
                _span(page_number, "VENDOR'S ADDRESS", 370.0, 40.0, width=120.0),
            ]
        )
    for index, (left_code, left_address, right_code, right_address) in enumerate(rows):
        y = 65.0 + index * 20.0
        for code, address, code_x, address_x in (
            (left_code, left_address, 25.0, 90.0),
            (right_code, right_address, 300.0, 370.0),
        ):
            if code:
                spans.append(_span(page_number, code, code_x, y, width=40.0))
            if address:
                for line_index, address_line in enumerate(address.splitlines()):
                    if address_line:
                        spans.append(
                            _span(
                                page_number,
                                address_line,
                                address_x,
                                y + line_index * 8.0,
                                width=120.0,
                            )
                        )
    return ParsedPage(page=page_number, text="", spans=spans)


def _context(*pages: ParsedPage) -> SimpleNamespace:
    parsed_pdf = ParsedPdf(
        page_count=len(pages),
        pages=list(pages),
        full_text="",
        is_signed=False,
    )
    return SimpleNamespace(
        runtime=SimpleNamespace(parsed_pdf=parsed_pdf, is_docx=False),
        targets=(),
    )


def _vendor_findings(context: SimpleNamespace):
    suggestions = operations.VENDOR_CODE_LIST.suggestions
    assert suggestions is not None
    return suggestions(context, {"control": "reference"})


def test_thales_code_and_address_are_checked_without_other_vendor_references() -> None:
    context = _context(
        _vendor_page(
            1,
            [("VF0001", "UNLISTED SUPPLIER", "VF9999", "ALSO UNLISTED")],
            title=True,
        ),
        _vendor_page(2, [("VF9111", _THALES_ADDRESS, "", "")]),
    )

    findings = _vendor_findings(context)

    assert findings is not None
    assert findings == []
    assert operations.VENDOR_CODE_LIST.execute(
        context, {"control": "reference"}
    ).status == "PASS"


def test_thales_address_allows_an_optional_trailing_revision_marker() -> None:
    page = _vendor_page(
        1,
        [("VF9111", _THALES_ADDRESS, "", "")],
        title=True,
        headers=False,
    )
    page.spans.extend(
        [
            _span(1, "CODE", 20.0, 40.0, width=30.0),
            _span(1, "VENDOR'S ADDRESS", 90.0, 40.0, width=110.0),
        ]
    )
    page.spans.append(_span(1, "R", 230.0, 65.0, width=8.0))

    findings = _vendor_findings(_context(page))

    assert findings == []


def test_thales_code_with_wrong_address_fails() -> None:
    context = _context(
        _vendor_page(
            1,
            [("VF9111", "THALES AVS FRANCE SAS\n75-77 AV MARCEL DASSAULT", "", "")],
            title=True,
        )
    )

    findings = _vendor_findings(context)

    assert findings is not None
    assert len(findings) == 1
    assert findings[0].expected == operations._THALES_VENDOR_ADDRESS
    assert findings[0].page == 1


def test_thales_address_with_wrong_code_fails() -> None:
    context = _context(
        _vendor_page(
            1,
            [("VF0001", _THALES_ADDRESS, "", "")],
            title=True,
        )
    )

    findings = _vendor_findings(context)

    assert findings is not None
    assert len(findings) == 1
    assert findings[0].expected == "VF9111"
    assert findings[0].page == 1


def test_other_vendor_rows_are_ignored_and_missing_thales_is_inconclusive() -> None:
    context = _context(
        _vendor_page(
            1,
            [("VF0001", "UNLISTED SUPPLIER", "VF0002", "ANOTHER SUPPLIER")],
            title=True,
        ),
    )

    findings = _vendor_findings(context)

    assert findings is not None
    assert findings == []
    assert operations.VENDOR_CODE_LIST.execute(
        context, {"control": "reference"}
    ).status == "INCONCLUSIVE"


def test_missing_vendor_table_is_inconclusive() -> None:
    context = _context(
        _vendor_page(1, [("VF9111", _THALES_ADDRESS, "", "")], headers=False)
    )

    result = operations.VENDOR_CODE_LIST.execute(context, {"control": "reference"})

    assert result.status == "INCONCLUSIVE"