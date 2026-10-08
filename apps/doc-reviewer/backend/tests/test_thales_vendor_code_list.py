from __future__ import annotations

from types import SimpleNamespace

from app.checks.thales_rules import operations
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, Span


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


def test_reference_check_handles_both_column_pairs_directions_and_continuation(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        operations,
        "_VENDOR_CODE_REFERENCE",
        {
            "VF0001": "NORTHWIND COMPONENTS",
            "VF0002": "BETA AVIATION",
            "VF0003": "ACME AEROSPACE",
            "VF0004": "DELTA SYSTEMS",
        },
    )
    context = _context(
        _vendor_page(
            1,
            [
                ("VF0001", "NORTHWIND COMPONENTS", "VF0002", "BETA AVIATION"),
                ("VF9999", "ACME AEROSPACE", "VF0003", "WRONG ADDRESS"),
            ],
            title=True,
        ),
        _vendor_page(2, [("VF0004", "WRONG ADDRESS", "", "")]),
    )

    findings = operations.VENDOR_CODE_LIST.suggestions(context, {"control": "reference"})

    assert findings is not None
    assert len(findings) == 3
    assert findings[0].expected == "VF0003"
    assert findings[0].page == 1
    assert findings[1].expected == "ACME AEROSPACE"
    assert findings[1].page == 1
    assert findings[2].expected == "DELTA SYSTEMS"
    assert findings[2].page == 2
    assert operations.VENDOR_CODE_LIST.execute(
        context, {"control": "reference"}
    ).status == "FAIL"


def test_reference_check_splits_embedded_codes_and_stops_at_copyright(monkeypatch) -> None:
    monkeypatch.setattr(
        operations,
        "_VENDOR_CODE_REFERENCE",
        {
            "VF9111": (
                "THALES AVS FRANCE SAS 75–77 AV MARCEL DASSAULT "
                "CAMPUS THALES BORDEAUX 33700 MERIGNAC FRANCE"
            ),
            "VN0521": (
                "SKELLESTA GUMISADRIKS ERSMARK SKELLEFTEA SWEDEN"
            ),
            "V71744": (
                "CHICAGO MINIATURE LIGHTING LLC 46615 RYAN CT NOVI "
                "MICHIGAN UNITED STATES"
            ),
        },
    )
    page = _vendor_page(66, [], title=True)
    page.spans.extend(
        [
            _span(66, "VF9111", 25.0, 65.0, width=42.0),
            _span(66, "THALES AVS FRANCE SAS", 90.0, 65.0, width=140.0),
            _span(66, "75–77 AV MARCEL DASSAULT", 90.0, 73.0, width=150.0),
            _span(66, "CAMPUS THALES BORDEAUX", 90.0, 81.0, width=140.0),
            _span(66, "33700 MERIGNAC", 90.0, 89.0, width=90.0),
            _span(66, "FRANCE", 90.0, 97.0, width=50.0),
            _span(
                66,
                "VN0521 SKELLESTA GUMISADRIKS",
                25.0,
                119.0,
                width=220.0,
            ),
            _span(66, "ERSMARK SKELLEFTEA", 90.0, 127.0, width=125.0),
            _span(66, "SWEDEN", 90.0, 135.0, width=50.0),
            _span(
                66,
                "V71744 CHICAGO MINIATURE LIGHTING LLC",
                25.0,
                159.0,
                width=250.0,
            ),
            _span(66, "46615 RYAN CT NOVI MICHIGAN", 90.0, 167.0, width=180.0),
            _span(66, "UNITED STATES", 90.0, 175.0, width=100.0),
            _span(
                66,
                "\uFFFD 1973-2026 THALES AVS FRANCE SAS. This document and any data included",
                25.0,
                230.0,
                width=250.0,
            ),
        ]
    )

    findings = operations.VENDOR_CODE_LIST.suggestions(
        _context(page), {"control": "reference"}
    )

    assert findings == []


def test_reference_check_requires_the_full_vendor_address(monkeypatch) -> None:
    monkeypatch.setattr(
        operations,
        "_VENDOR_CODE_REFERENCE",
        {
            "VF0001": (
                "AFNOR (ASSOCIATION FRANCAISE DE NORMALISATION) "
                "11 RUE FRANCIS DE PRESSENSE SAINT DENIS FRANCE"
            ),
            "VF0002": "M.F.O.E.M. (MANUFACTURING EXAMPLE) 31 RUE RASPAIL FRANCE",
        },
    )
    context = _context(
        _vendor_page(
            1,
            [
                (
                    "VF0001",
                    "AFNOR 11 RUE FRANCIS DE PRESSENSE SAINT DENIS FRANCE",
                    "VF0002",
                    "M.F.O.E.M. 31 RUE RASPAIL FRANCE",
                )
            ],
            title=True,
        )
    )

    findings = operations.VENDOR_CODE_LIST.suggestions(context, {"control": "reference"})

    assert len(findings) == 2
    assert findings[0].expected == operations._VENDOR_CODE_REFERENCE["VF0001"]
    assert findings[1].expected == operations._VENDOR_CODE_REFERENCE["VF0002"]


def test_reference_check_accepts_company_names_and_road_terms(monkeypatch) -> None:
    monkeypatch.setattr(
        operations,
        "_VENDOR_CODE_REFERENCE",
        {
            "VF0001": "JOINT FRANCAIS 7 RUE PIERRE DREYFUS 92110 CLICHY FRANCE",
            "VF0002": "VIRAX S.A. 39 QUAI DE MARNE 51200 EPERNAY FRANCE",
        },
    )
    context = _context(
        _vendor_page(
            1,
            [
                (
                    "VF0001",
                    "JOINT FRANCAIS 7 RUE PIERRE DREYFUS 92110 CLICHY FRANCE",
                    "VF0002",
                    "VIRAX S.A. 39 QUAI DE MARNE 51200 EPERNAY FRANCE",
                )
            ],
            title=True,
        )
    )

    findings = operations.VENDOR_CODE_LIST.suggestions(context, {"control": "reference"})

    assert findings == []


def test_reference_check_stops_before_a_page_without_vendor_headers(monkeypatch) -> None:
    monkeypatch.setattr(
        operations,
        "_VENDOR_CODE_REFERENCE",
        {
            "VF0110": "AFNOR (ASSOCIATION FRANCAISE DE NORMALISATION)",
            "VF0229": "AERO RUE PORTE DE BUC 78000 VERSAILLES",
        },
    )
    context = _context(
        _vendor_page(
            1,
            [("VF0110", "AFNOR (ASSOCIATION FRANCAISE DE NORMALISATION)", "", "")],
            title=True,
        ),
        _vendor_page(
            2,
            [("VF0229", "WRONG ADDRESS", "", "")],
            headers=False,
        ),
    )

    findings = operations.VENDOR_CODE_LIST.suggestions(context, {"control": "reference"})

    assert findings == []


def test_reference_check_is_inconclusive_until_reference_is_populated(monkeypatch) -> None:
    monkeypatch.setattr(operations, "_VENDOR_CODE_REFERENCE", {})
    context = _context(
        _vendor_page(1, [("VF0001", "NORTHWIND COMPONENTS", "", "")], title=True)
    )

    result = operations.VENDOR_CODE_LIST.execute(context, {"control": "reference"})

    assert result.status == "INCONCLUSIVE"