"""Cross-source detection of the pages a THALES revision modified."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.checks.client_registry import load_active_client_configuration
from app.checks.thales_rules import revision_engine as revision
from app.checks.thales_rules.page_classifier import classify_pages
from app.checks.thales_rules.rules import REVISION_RULE_DEFINITIONS
from app.core.compiled_rule_executor import execute_pdf_rules as _execute_pdf_rules
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, PdfWord, Span


_TEST_CLIENT_BUNDLE = load_active_client_configuration().bundle
_REVISION_RULES = [
    definition.compiled_rule for definition in REVISION_RULE_DEFINITIONS
]


def execute_pdf_rules(*args: Any, **kwargs: Any):
    kwargs.setdefault("client_operations", _TEST_CLIENT_BUNDLE.operations)
    kwargs.setdefault("client_entities", _TEST_CLIENT_BUNDLE.mapping.entities)
    return _execute_pdf_rules(*args, **kwargs)


_COPYRIGHT = (
    "\u00a9 1966-2026 THALES AVS FRANCE SAS. This document and any data included "
    "are the property of THALES AVS FRANCE SAS."
)
_REVISION_DATE = "JUL 27/26"
_DOCUMENT = SimpleNamespace(
    meta_revision_date=_REVISION_DATE,
    meta_first_issue_date="JUL 1966",
    meta_last_issue_date="MAR 77",
)


def _span(text: str, x: float, y: float, page: int) -> Span:
    return Span(
        text=text,
        bbox=(x, y - 5.0, x + 6.0 * len(text), y + 5.0),
        page=page,
        font="Arial",
        size=10.0,
    )


def _word(text: str, x_position: float, center_y: float, word_index: int) -> PdfWord:
    return PdfWord(
        text=text,
        bbox=(
            x_position,
            center_y - 5.0,
            x_position + 6.0 * len(text),
            center_y + 5.0,
        ),
        block_index=0,
        line_index=0,
        word_index=word_index,
    )


def _footer(page: int, label: str, date: str, y: float = 756.0) -> list[Span]:
    return [
        _span(_COPYRIGHT, 85.9, y, page),
        _span(label, 500.0, y, page),
        _span(date, 507.0, y + 16.0, page),
    ]


def _page(page: int, spans: list[Span]) -> ParsedPage:
    return ParsedPage(
        page=page,
        text="\n".join(span.text for span in spans),
        spans=spans,
    )


def _ror_page(revision_date: str, insertion_date: str, page: int = 1) -> ParsedPage:
    spans = [
        _span("RECORD OF REVISIONS", 100.0, 100.0, page),
        _span("REVISION DATE", 200.0, 140.0, page),
        _span("INSERTION DATE", 350.0, 140.0, page),
        _span(revision_date, 200.0, 170.0, page),
        _span(insertion_date, 350.0, 170.0, page),
    ]
    return _page(page, spans)


def _highlights_page(rows: list[tuple[str, str, str]], page: int = 1) -> ParsedPage:
    """One (subject, page range, status) block per row, laid out like the PDF."""
    spans = [
        _span("HIGHLIGHTS", 293.9, 137.6, page),
        _span("Chapter/Section and Page No", 105.8, 229.3, page),
        _span("Designation", 292.0, 229.3, page),
        _span("Description of Change", 399.0, 229.3, page),
    ]
    y = 250.0
    for subject, pages_text, status in rows:
        spans.append(_span(subject, 90.7, y, page))
        spans.append(_span(pages_text, 90.7, y + 14.0, page))
        if status:
            spans.append(_span(status, 322.2, y + 14.0, page))
        spans.append(_span("Updated.", 366.4, y + 14.0, page))
        y += 42.0
    spans.extend(_footer(page, "Highlights Page 1", _REVISION_DATE))
    return _page(page, spans)


def _lep_page(
    left: list[tuple[str, str, str]],
    right: list[tuple[str, str, str]],
    page: int = 2,
    columns: tuple[tuple[float, float, float, float], ...] = (
        (86.4, 114.7, 194.2, 249.5),
        (329.4, 357.0, 435.4, 492.1),
    ),
) -> ParsedPage:
    """`left`/`right` hold (subject, page id, date) for each column group.

    An entry with an empty page id renders a subject-only row, which is how
    the real table wraps a long section name over two lines. `columns` gives
    the (subject, prefix, page, date) abscissa of each group.
    """
    spans = [_span("LIST OF EFFECTIVE PAGES", 254.9, 95.1, page)]
    for subject_x, _prefix_x, page_x, date_x in columns:
        spans.append(_span("SUBJECT", subject_x, 122.2, page))
        spans.append(_span("PAGE", page_x + 0.2, 122.2, page))
        spans.append(_span("DATE", date_x + 7.9, 122.2, page))
    for group, (subject_x, prefix_x, page_x, date_x) in zip((left, right), columns):
        y = 151.0
        for subject, page_id, date in group:
            if subject:
                spans.append(_span(subject, subject_x, y, page))
            if page_id:
                prefix, _, number = page_id.rpartition(" ")
                if prefix:
                    spans.append(_span(prefix, prefix_x, y, page))
                spans.append(_span(number, page_x, y, page))
                spans.append(_span(date, date_x, y, page))
            y += 14.3
    spans.extend(_footer(page, "LEP Page 1", _REVISION_DATE))
    return _page(page, spans)


def _document(pages: list[ParsedPage]) -> ParsedPdf:
    return ParsedPdf(
        page_count=len(pages),
        pages=pages,
        full_text="\n".join(page.text for page in pages),
        is_signed=False,
    )


def _consistent_document() -> ParsedPdf:
    return _document(
        [
            _highlights_page(
                [
                    ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
                    ("Repair", "Pages 401 to 402", "R"),
                ]
            ),
            _lep_page(
                left=[
                    ("List of Effec-", "", ""),
                    ("tive Pages", "", ""),
                    ("", "LEP 1", f"{_REVISION_DATE} *"),
                    ("", "LEP 2", "Blank     *"),
                    ("Repair", "401", f"{_REVISION_DATE} *"),
                    ("", "402", f"{_REVISION_DATE} *"),
                ],
                right=[("Assembly", "501", "JUL 66")],
            ),
            _page(3, _footer(3, "Page 401", _REVISION_DATE)),
            _page(4, _footer(4, "Page 402", _REVISION_DATE)),
            _page(5, _footer(5, "Page 501", "JUL 66")),
        ]
    )


def _lep_with(
    *rows: tuple[str, str, str],
    right: tuple[str, str, str] = ("Assembly", "501", "JUL 66"),
    columns: tuple[tuple[float, float, float, float], ...] | None = None,
) -> ParsedPage:
    """Rebuild the LEP page, keeping the two entries describing itself."""
    left = [
        ("List of Effec-", "", ""),
        ("tive Pages", "", ""),
        ("", "LEP 1", f"{_REVISION_DATE} *"),
        ("", "LEP 2", "Blank     *"),
        *rows,
    ]
    if columns is None:
        return _lep_page(left=left, right=[right])
    return _lep_page(left=left, right=[right], columns=columns)


def _state(parsed: ParsedPdf, document: object = _DOCUMENT) -> revision.RevisionState:
    return revision.build_revision_state(parsed, document)


def _findings(
    parsed: ParsedPdf, document: object = _DOCUMENT
) -> list[revision.RevisionFinding]:
    return _state(parsed, document).findings


def _codes(parsed: ParsedPdf, document: object = _DOCUMENT) -> list[str]:
    return [finding.control for finding in _findings(parsed, document)]


def test_page_key_normalization_unifies_the_three_sources() -> None:
    assert revision.normalize_page_key("ROR Page 1") == "ROR 1"
    assert revision.normalize_page_key("Page 401") == "401"
    assert revision.normalize_page_key("TP 1") == "TP 1"
    assert revision.normalize_page_key("INTRO 1101 Page 1") == "INTRO 1101 1"
    assert revision.normalize_page_key("NI/NUM 1101 Page 2") == "NI/NUM 1101 2"
    assert revision.expand_page_range("Pages 701 to 704") == ("701", "702", "703", "704")
    assert revision.expand_page_range("TP 1 to TP 2") == ("TP 1", "TP 2")
    assert revision.expand_page_range("ROR Page 1 to ROR Page 2") == ("ROR 1", "ROR 2")
    assert revision.expand_page_range(
        "INTRO 1101 Page 1 to INTRO Page 2"
    ) == ("INTRO 1101 1", "INTRO 1101 2")
    assert revision.expand_page_range(
        "Pages 1101-1 to 1101-2"
    ) == ("1101-1", "1101-2")
    assert revision.expand_page_range("Page  1101-1") == ("1101-1",)


def test_highlights_page_range_keeps_spans_past_the_header_boundary() -> None:
    page = _page(
        1,
        [
            _span("Chapter/Section and Page No", 54.0, 100.0, 1),
            _span("Designation", 285.0, 100.0, 1),
            _span("Description of Change", 366.0, 100.0, 1),
            _span("Introduction", 90.7, 120.0, 1),
            _span("INTRO", 90.7, 140.0, 1),
            _span("Page 1", 126.7, 140.0, 1),
            _span("to INTRO", 168.7, 140.0, 1),
            _span("Page 2", 222.7, 140.0, 1),
            _span("N", 322.2, 140.0, 1),
            _span("Shop verification added.", 366.4, 140.0, 1),
        ],
    )

    entry = revision.extract_highlights(page)[0]

    assert entry.pages_text == "INTRO Page 1 to INTRO Page 2"
    assert entry.page_keys == ("INTRO 1", "INTRO 2")


def test_highlights_extracts_row_and_illustrated_parts_list_descriptions() -> None:
    page = _page(
        1,
        [
            _span("Chapter/Section and Page No", 54.0, 100.0, 1),
            _span("Designation", 285.0, 100.0, 1),
            _span("Description of Change", 366.0, 100.0, 1),
            _span("Illustrated Parts List", 90.7, 120.0, 1),
            _span("Revised to reflect", 366.0, 120.0, 1),
            _span("this revision.", 480.0, 120.0, 1),
            _span("INTRO 1101 Page 1 to INTRO Page 2", 90.7, 140.0, 1),
            _span("R", 322.2, 140.0, 1),
            _span("INTRO 1101 Page 3 to INTRO Page 4", 90.7, 160.0, 1),
            _span("R", 322.2, 160.0, 1),
            _span("Repair", 90.7, 180.0, 1),
            _span("Page 601", 90.7, 200.0, 1),
            _span("D", 322.2, 200.0, 1),
            _span("Chapter deleted", 366.0, 200.0, 1),
        ],
    )

    entries = revision.extract_highlights(page)

    assert len(entries) == 3
    assert entries[0].subject == "Illustrated Parts List"
    assert entries[0].subject_description == "Revised to reflect this revision."
    assert entries[0].description == ""
    assert entries[0].subject_description_bbox is not None
    assert entries[1].status == "R"
    assert entries[1].subject_description == "Revised to reflect this revision."
    assert entries[1].description == ""
    assert entries[2].status == "D"
    assert entries[2].description == "Chapter deleted"


def test_compound_highlights_lep_and_footer_names_match() -> None:
    highlights = _highlights_page(
        [
            ("Illustrated Parts List", "INTRO 1101 Page 1 to INTRO Page 2", "R"),
            ("Illustrated Parts List", "NI/NUM 1101 Page 1", "R"),
        ],
        page=1,
    )
    lep = _lep_page(
        left=[
            ("INTRO 1101", "1", f"{_REVISION_DATE} *"),
            ("", "2", f"{_REVISION_DATE} *"),
            ("NI/NUM 1101", "1", f"{_REVISION_DATE} *"),
        ],
        right=[],
        page=2,
    )
    parsed = _document(
        [
            highlights,
            lep,
            _page(3, _footer(3, "INTRO 1101 Page 1", _REVISION_DATE)),
            _page(4, _footer(4, "INTRO 1101 Page 2", _REVISION_DATE)),
            _page(5, _footer(5, "NI/NUM 1101 Page 1", _REVISION_DATE)),
        ]
    )

    state = _state(parsed)

    assert [page.is_modified for page in parsed.pages[2:]] == [True, True, True]
    assert not any(
        finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
        for finding in state.findings
    )


def test_footer_reassembles_section_page_and_split_date_spans() -> None:
    page = _page(
        1,
        [
            _span("INTRO", 459.2, 740.0, 1),
            _span("1101", 492.0, 740.0, 1),
            _span("Page", 524.0, 740.0, 1),
            _span("2", 556.0, 740.0, 1),
            _span("Aug.", 467.9, 760.0, 1),
            _span("30/75", 498.0, 760.0, 1),
        ],
    )

    footer = revision.extract_footer(page)

    assert footer is not None
    assert footer.page_key == "INTRO 1101 2"
    assert footer.date is not None
    assert footer.date.same_as(revision.parse_date("AUG 30/75"))
    assert footer.date_text == "Aug. 30/75"


def test_footer_reassembles_month_abbreviation_with_extraction_artifact() -> None:
    page = _page(
        79,
        [
            _span(_COPYRIGHT, 85.9, 756.0, 79),
            _span("Page 1104-0", 453.3, 747.6, 79),
            _span("Aug_.", 458.86, 763.2, 79),
            _span("30/75", 488.98, 763.2, 79),
        ],
    )

    footer = revision.extract_footer(page)

    assert footer is not None
    assert footer.date is not None
    assert footer.date.same_as(revision.parse_date("AUG 30/75"))
    assert footer.date_text == "Aug_. 30/75"


def test_footer_reassembles_split_day_and_year_spans() -> None:
    page = _page(
        3,
        [
            _span(_COPYRIGHT, 85.9, 756.0, 3),
            _span("TP 1", 500.0, 756.0, 3),
            _span("JUL", 507.34, 771.36, 3),
            _span("30", 531.34, 771.36, 3),
            _span("/", 543.34, 771.36, 3),
            _span("26", 549.34, 771.36, 3),
        ],
    )

    footer = revision.extract_footer(page)

    assert footer is not None
    assert footer.date is not None
    assert footer.date.same_as(revision.parse_date("JUL 30/26"))
    assert footer.date_text == "JUL 30 / 26"
    assert footer.date_bbox == (507.34, 766.36, 561.34, 776.36)


def test_footer_reassembles_page_number_split_across_spans() -> None:
    page = _page(
        40,
        [
            _span(_COPYRIGHT, 85.9, 756.0, 40),
            _span("Page", 477.58, 756.0, 40),
            _span("50", 507.58, 756.0, 40),
            _span("2", 519.58, 756.0, 40),
            _span("JUL 30/26", 507.34, 772.0, 40),
        ],
    )
    page.words = [
        _word("Page", 477.58, 756.0, 0),
        _word("502", 507.58, 756.0, 1),
        _word("JUL", 507.34, 772.0, 2),
        _word("30/26", 531.34, 772.0, 3),
    ]

    footer = revision.extract_footer(page)

    assert footer is not None
    assert footer.page_key == "502"
    assert footer.label_text == "Page 502"


def test_ror_detection_requires_the_full_record_of_revisions_title() -> None:
    shorthand_page = _page(1, [_span("ROR", 100.0, 100.0, 1)])
    highlights_subject_page = _page(
        1,
        [
            _span("T", 100.0, 20.0, 1),
            _span("HIGHLIGHTS", 100.0, 100.0, 1),
            _span("Record of Revisions", 100.0, 279.0, 1),
            _span("footer", 100.0, 780.0, 1),
        ],
    )
    lep_subject_page = _page(
        9,
        [
            _span("T", 100.0, 20.0, 9),
            _span("LIST OF EFFECTIVE PAGES", 100.0, 100.0, 9),
            _span("Record of", 100.0, 200.0, 9),
            _span("Revisions", 100.0, 214.0, 9),
            _span("footer", 100.0, 780.0, 9),
        ],
    )

    assert revision._special_footer_section(shorthand_page) is None
    assert revision._special_footer_section(highlights_subject_page) == "HIGHLIGHTS"
    assert revision._special_footer_section(lep_subject_page) == "LEP"
    assert revision._special_footer_section(_ror_page("JUL 14/26", "JUL 26")) == "ROR"


def test_ror_insertion_date_uses_revision_day_and_rolls_the_year() -> None:
    for revision_date, insertion_date in (
        ("JUL 14/26", "JUL 26"),
        ("JUL 15/26", "AUG 26"),
        ("DEC 15/26", "JAN 27"),
    ):
        document = SimpleNamespace(
            meta_revision_date=revision_date,
            meta_first_issue_date="JUL 1966",
            meta_last_issue_date="MAR 77",
        )
        assert (
            _codes(_document([_ror_page(revision_date, insertion_date)]), document)
            == []
        )


def test_ror_insertion_date_mismatch_is_reported_with_the_expected_month() -> None:
    document = SimpleNamespace(
        meta_revision_date="JUL 15/26",
        meta_first_issue_date="JUL 1966",
        meta_last_issue_date="MAR 77",
    )
    findings = _findings(
        _document([_ror_page("JUL 15/26", "JUL 26")]), document
    )

    assert [finding.control for finding in findings] == [revision.ROR_INSERTION_DATE]
    assert findings[0].original == "JUL 26"
    assert findings[0].proposed == "AUG 26"


def test_ror_revision_date_must_match_the_highlights_revision_date() -> None:
    assert _codes(_document([_ror_page(_REVISION_DATE, "AUG 26")])) == []

    findings = _findings(_document([_ror_page("JUN 27/26", "JUL 26")]))

    assert [finding.control for finding in findings] == [revision.ROR_REVISION_DATE]
    assert findings[0].original == "JUN 27/26"
    assert findings[0].proposed == _REVISION_DATE


def test_page_keys_accept_any_section_abbreviation() -> None:
    assert revision.normalize_page_key("SB Page 3") == "SB 3"
    assert revision.normalize_page_key("Highlights Page 1") == "HIGHLIGHTS 1"
    assert revision.normalize_page_key("1101-0") == "1101-0"
    # A date, a CMM number and a part number are not page ids.
    assert revision.normalize_page_key("JUL 66") is None
    assert revision.normalize_page_key("JUL 27/26") is None
    assert revision.normalize_page_key("79-30-02") is None
    assert revision.normalize_page_key("1-879-SB") is None


def test_extraction_follows_the_header_columns_not_fixed_positions() -> None:
    """Same table, different page size, margins and column widths."""
    reference = _consistent_document()
    moved = _consistent_document()
    moved.pages[1] = _lep_with(
        ("Repair", "401", f"{_REVISION_DATE} *"),
        ("", "402", f"{_REVISION_DATE} *"),
        columns=((40.0, 72.0, 150.0, 205.0), (300.0, 332.0, 410.0, 465.0)),
    )

    assert _codes(moved) == _codes(reference) == []
    assert [(entry.page_key, entry.date_text) for entry in _state(moved).lep] == [
        (entry.page_key, entry.date_text) for entry in _state(reference).lep
    ]


def test_lep_column_group_count_is_read_from_the_header() -> None:
    parsed = _consistent_document()
    parsed.pages[1] = _lep_page(
        left=[
            ("List of Effec-", "", ""),
            ("tive Pages", "", ""),
            ("", "LEP 1", f"{_REVISION_DATE} *"),
            ("", "LEP 2", "Blank     *"),
            ("Repair", "401", f"{_REVISION_DATE} *"),
            ("", "402", f"{_REVISION_DATE} *"),
            ("Assembly", "501", "JUL 66"),
        ],
        right=[],
        columns=((86.4, 114.7, 194.2, 249.5),),
    )

    assert _codes(parsed) == []
    assert [entry.page_key for entry in _state(parsed).lep] == [
        "LEP 1",
        "LEP 2",
        "401",
        "402",
        "501",
    ]


def test_dates_compare_across_their_two_written_forms() -> None:
    july_1966 = revision.parse_date("JUL 1966")
    july_66 = revision.parse_date("JUL 66")
    july_27_26 = revision.parse_date("JUL 27/26")
    march_77 = revision.parse_date("MAR 77")
    assert july_1966 is not None
    assert july_66 is not None
    assert july_27_26 is not None
    assert march_77 is not None

    assert july_1966.same_as(july_66)
    assert not july_27_26.same_as(july_66)
    assert july_27_26.sort_key > march_77.sort_key


def test_abbreviated_month_date_with_period_is_recognized() -> None:
    abbreviated = revision.parse_date("Aug. 30/75")
    unpunctuated = revision.parse_date("AUG 30/75")
    assert abbreviated is not None
    assert unpunctuated is not None

    assert abbreviated.same_as(unpunctuated)


def test_lep_rows_are_split_into_two_independent_entries() -> None:
    state = revision.build_revision_state(_consistent_document(), _DOCUMENT)

    assert [(entry.subject, entry.page_key, entry.starred) for entry in state.lep] == [
        ("List of Effective Pages", "LEP 1", True),
        ("List of Effective Pages", "LEP 2", True),
        ("Repair", "401", True),
        ("Repair", "402", True),
        ("Assembly", "501", False),
    ]


def test_consistent_document_reports_nothing_and_marks_modified_pages() -> None:
    parsed = _consistent_document()

    assert _codes(parsed) == []
    assert [page.is_modified for page in parsed.pages] == [True, True, True, True, False]


def test_first_page_of_each_revision_section_is_always_modified() -> None:
    title_page = _page(3, [_span("Title page body", 100.0, 120.0, 3)])
    title_page.page_type = "TP1"
    parsed = _document(
        [
            _highlights_page([], page=1),
            _lep_page(left=[], right=[], page=2),
            title_page,
            _ror_page(_REVISION_DATE, "JUL 66", page=4),
        ]
    )

    state = _state(parsed)

    assert state.available is False
    assert [page.is_modified for page in parsed.pages] == [True, True, True, True]


def test_highlights_page_2_is_forced_modified_and_unmatched_pages_default_unchanged() -> None:
    parsed = _consistent_document()
    second_highlights = _highlights_page([], page=2)
    for span in second_highlights.spans:
        if span.text == "Highlights Page 1":
            span.text = "Highlights Page 2"
    second_highlights.text = "\n".join(span.text for span in second_highlights.spans)
    parsed.pages.insert(1, second_highlights)
    parsed.pages.append(_page(7, _footer(7, "Page 999", "JUL 66")))
    for page_number, page in enumerate(parsed.pages, start=1):
        page.page = page_number
        for span in page.spans:
            span.page = page_number
    parsed.page_count = len(parsed.pages)

    state = _state(parsed)

    assert state.available is True
    assert parsed.pages[1].is_modified is True
    assert parsed.pages[-1].is_modified is False


def test_current_footer_date_alone_does_not_mark_a_page_modified() -> None:
    parsed = _document([_page(1, _footer(1, "Page 401", _REVISION_DATE))])

    state = _state(parsed)

    assert state.available is False
    assert parsed.pages[0].is_modified is None


def test_current_lep_date_without_highlights_or_footer_agreement_is_undecided() -> None:
    parsed = _consistent_document()
    parsed.pages[1] = _lep_page(
        left=[
            ("List of Effec-", "", ""),
            ("tive Pages", "", ""),
            ("", "LEP 1", f"{_REVISION_DATE} *"),
            ("", "LEP 2", "Blank     *"),
            ("Repair", "401", f"{_REVISION_DATE} *"),
            ("", "402", f"{_REVISION_DATE} *"),
        ],
        right=[("Assembly", "501", _REVISION_DATE)],
        page=2,
    )

    _state(parsed)

    assert parsed.pages[4].is_modified is None


def test_page_state_requires_agreement_between_all_three_sources() -> None:
    cases = (
        ("R", _REVISION_DATE, True, _REVISION_DATE, True),
        ("N", _REVISION_DATE, True, _REVISION_DATE, True),
        ("R", _REVISION_DATE, False, _REVISION_DATE, None),
        ("R", _REVISION_DATE, True, "JUL 66", None),
        ("U", _REVISION_DATE, True, _REVISION_DATE, None),
        ("U", "JUL 66", False, "JUL 66", False),
    )

    for status, lep_date, starred, footer_date, expected in cases:
        parsed = _consistent_document()
        parsed.pages[0] = _highlights_page(
            [
                ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
                ("Repair", "Pages 401 to 402", status),
            ]
        )
        starred_date = f"{lep_date} *" if starred else lep_date
        parsed.pages[1] = _lep_with(
            ("Repair", "401", starred_date),
            ("", "402", f"{_REVISION_DATE} *"),
        )
        parsed.pages[2] = _page(3, _footer(3, "Page 401", footer_date))

        _state(parsed)

        assert parsed.pages[2].is_modified is expected


def test_missing_lep_footer_page_number_is_reported() -> None:
    parsed = _consistent_document()
    second_lep = _lep_page(left=[], right=[], page=3)
    second_lep.spans = [span for span in second_lep.spans if span.text != "LEP Page 1"]
    second_lep.text = "\n".join(span.text for span in second_lep.spans)
    parsed.pages.insert(2, second_lep)
    for page_number, page in enumerate(parsed.pages, start=1):
        page.page = page_number
        for span in page.spans:
            span.page = page_number
    parsed.page_count = len(parsed.pages)

    findings = _findings(parsed)
    page_number_findings = [
        finding for finding in findings if finding.control == revision.FOOTER_PAGE_NUMBER
    ]

    assert [(finding.page, finding.proposed) for finding in page_number_findings] == [
        (3, "LEP Page 2")
    ]
    assert revision.MODIFIED_PAGE_ABSENT not in _codes(parsed)

    _results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)

    assert [
        (raw.rule_code, raw.page, raw.original, raw.proposed)
        for raw in raws
        if raw.rule_code == "CUSTOM_FOOTER_PAGE_NUMBER"
    ] == [("CUSTOM_FOOTER_PAGE_NUMBER", 3, "", "LEP Page 2")]


def test_footer_page_number_ignores_cached_findings_outside_selected_pages() -> None:
    from app.checks.thales_rules import operations
    from app.core.page_range import filter_pdf_pages

    parsed = _consistent_document()
    unchanged_page = _page(
        6,
        [
            _span(_COPYRIGHT, 85.9, 756.0, 6),
            _span(_REVISION_DATE, 507.0, 772.0, 6),
        ],
    )
    parsed.pages.append(unchanged_page)
    parsed.page_count = 6
    state = _state(parsed)
    unchanged_page.is_modified = False

    assert any(
        finding.control == revision.FOOTER_PAGE_NUMBER and finding.page == 6
        for finding in state.findings
    )
    partial = filter_pdf_pages(parsed, [1])
    setattr(partial, operations._REVISION_STATE_ATTR, state)
    footer_rule = next(
        rule for rule in _REVISION_RULES if rule.id == "CUSTOM_FOOTER_PAGE_NUMBER"
    )

    results, raws = execute_pdf_rules(partial, [footer_rule], document=_DOCUMENT)

    assert [(result.rule_id, result.status) for result in results] == [
        ("CUSTOM_FOOTER_PAGE_NUMBER", "PASS")
    ]
    assert raws == []


def test_missing_footer_page_number_anchors_on_line_above_revision_date() -> None:
    parsed = _consistent_document()
    page = parsed.pages[2]
    page.spans = [span for span in page.spans if span.text != "Page 401"]
    page.text = "\n".join(span.text for span in page.spans)

    findings = [
        finding
        for finding in _findings(parsed)
        if finding.control == revision.FOOTER_PAGE_NUMBER
    ]

    assert len(findings) == 1
    assert findings[0].bbox == (507.0, 756.0, 561.0, 766.0)


def test_missing_tp1_footer_page_number_is_reported_on_the_title_page() -> None:
    def title_page(page_number: int, marker: str | None) -> ParsedPage:
        spans = [
            _span("OVERHAUL MANUAL", 100.0, 120.0, page_number),
            _span("PART NUMBER", 100.0, 140.0, page_number),
            _span(_COPYRIGHT, 85.9, 756.0, page_number),
            _span("JUL 27/26", 507.0, 772.0, page_number),
        ]
        if marker is not None:
            spans.insert(2, _span(marker, 500.0, 756.0, page_number))
        return _page(page_number, spans)

    parsed = _consistent_document()
    parsed.pages[0:0] = [title_page(1, None), title_page(2, "TP 2")]
    for page_number, page in enumerate(parsed.pages, start=1):
        page.page = page_number
        for span in page.spans:
            span.page = page_number
    parsed.page_count = len(parsed.pages)

    findings = _findings(parsed)

    assert [
        (finding.page, finding.proposed)
        for finding in findings
        if finding.control == revision.FOOTER_PAGE_NUMBER
    ] == [(1, "TP 1")]


def test_missing_highlights_and_ror_footer_numbers_follow_section_order() -> None:
    def footer_without_label(page_number: int) -> list[Span]:
        return [
            _span(_COPYRIGHT, 85.9, 756.0, page_number),
            _span(_REVISION_DATE, 507.0, 772.0, page_number),
        ]

    highlights_page_2 = _highlights_page([], page=2)
    highlights_page_2.spans = [
        span for span in highlights_page_2.spans if span.text != "Highlights Page 1"
    ]
    highlights_page_2.text = "\n".join(span.text for span in highlights_page_2.spans)
    ror_page_1 = _page(
        3,
        [_span("RECORD OF REVISIONS", 100.0, 120.0, 3)]
        + _footer(3, "ROR Page 1", _REVISION_DATE),
    )
    ror_page_2 = _page(
        4,
        [_span("RECORD OF REVISIONS", 100.0, 120.0, 4)]
        + footer_without_label(4),
    )
    parsed = _consistent_document()
    parsed.pages[1:1] = [highlights_page_2, ror_page_1, ror_page_2]
    for page_number, page in enumerate(parsed.pages, start=1):
        page.page = page_number
        for span in page.spans:
            span.page = page_number
    parsed.page_count = len(parsed.pages)

    findings = _findings(parsed)

    assert [
        (finding.page, finding.proposed)
        for finding in findings
        if finding.control == revision.FOOTER_PAGE_NUMBER
    ] == [(2, "Highlights Page 2"), (4, "ROR Page 2")]


def test_revised_page_without_star_in_the_lep_is_reported() -> None:
    parsed = _consistent_document()
    parsed.pages[1] = _lep_with(
        ("Repair", "401", _REVISION_DATE), ("", "402", f"{_REVISION_DATE} *")
    )

    findings = _findings(parsed)

    assert [finding.control for finding in findings] == [revision.LEP_STAR]
    assert findings[0].proposed == f"{_REVISION_DATE} *"


def test_star_without_a_revised_status_in_the_highlights_is_reported() -> None:
    parsed = _consistent_document()
    parsed.pages[1] = _lep_with(
        ("Repair", "401", f"{_REVISION_DATE} *"),
        ("", "402", f"{_REVISION_DATE} *"),
        right=("Assembly", "501", "JUL 66 *"),
    )

    findings = _findings(parsed)

    assert [finding.control for finding in findings] == [revision.UNDECLARED_STAR]
    assert findings[0].proposed == "JUL 66"


def test_highlights_r_and_n_are_both_valid_when_lep_and_footer_show_revision() -> None:
    for status in ("R", "N"):
        parsed = _consistent_document()
        parsed.pages[0] = _highlights_page(
            [
                ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
                ("Repair", "Pages 401 to 402", status),
            ]
        )

        findings = [
            finding
            for finding in _findings(parsed)
            if finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
        ]

        assert findings == []


def test_highlights_r_or_n_conflicts_with_agreeing_unchanged_lep_and_footer() -> None:
    for status in ("R", "N"):
        parsed = _consistent_document()
        parsed.pages[0] = _highlights_page(
            [
                ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
                ("Repair", "Pages 401 to 402", status),
            ]
        )
        parsed.pages[1] = _lep_with(
            ("Repair", "401", "JUL 66"), ("", "402", "JUL 66")
        )
        parsed.pages[2] = _page(3, _footer(3, "Page 401", "JUL 66"))
        parsed.pages[3] = _page(4, _footer(4, "Page 402", "JUL 66"))

        findings = [
            finding
            for finding in _findings(parsed)
            if finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
        ]
        highlight_entry = next(
            entry for entry in _state(parsed).highlights if entry.subject == "Repair"
        )

        assert len(findings) == 1
        assert findings[0].original == status
        assert findings[0].bbox == highlight_entry.status_bbox
        assert "inchangée" in findings[0].message
        assert "U" in findings[0].message


def test_highlights_u_conflicts_with_star_and_current_lep_and_footer_dates() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "U"),
        ]
    )

    findings = [
        finding
        for finding in _findings(parsed)
        if finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
    ]
    highlight_entry = next(
        entry for entry in _state(parsed).highlights if entry.subject == "Repair"
    )

    assert len(findings) == 1
    assert findings[0].original == "U"
    assert findings[0].bbox == highlight_entry.status_bbox
    assert "R" in findings[0].message
    assert "N" in findings[0].message


def test_compiled_highlights_status_rule_comments_on_the_designation_cell() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "U"),
        ]
    )

    _results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)
    status_raws = [
        raw for raw in raws if raw.rule_code == "CUSTOM_REVISION_HIGHLIGHTS_STATUS"
    ]
    highlight_entry = next(
        entry for entry in _state(parsed).highlights if entry.subject == "Repair"
    )

    assert len(status_raws) == 1
    assert status_raws[0].page == 1
    assert status_raws[0].original == "U"
    assert status_raws[0].bbox == highlight_entry.status_bbox
    assert status_raws[0].severity == "warning"


def test_compiled_highlights_status_rule_uses_previous_lep() -> None:
    current = _consistent_document()
    current.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Page 401", "N"),
            ("Assembly", "Page 503", "R"),
            ("Deleted page", "Page 502", "D"),
            ("New page", "Page 504", "N"),
            ("Old unchanged page", "Page 406", "U"),
            ("Missing old unchanged page", "Page 505", "U"),
            ("Missing deleted page", "Page 506", "D"),
        ]
    )
    previous = _document(
        [
            _lep_page(
                left=[
                    ("Repair", "401", "JUL 66"),
                    ("Old unchanged page", "406", "JUL 66"),
                ],
                right=[("Deleted page", "502", "JUL 66")],
            )
        ]
    )
    status_rule = next(
        rule for rule in _REVISION_RULES if rule.id == "CUSTOM_REVISION_HIGHLIGHTS_STATUS"
    )

    _results, raws = execute_pdf_rules(
        current,
        [status_rule],
        document=_DOCUMENT,
        previous_revision_pdf=previous,
    )
    status_raws = [raw for raw in raws if raw.rule_code == status_rule.id]

    assert sorted((raw.original, raw.page) for raw in status_raws) == [
        ("D", 1),
        ("N", 1),
        ("R", 1),
        ("U", 1),
    ]
    assert all("LEP N-1" in raw.message for raw in status_raws)


def test_compiled_highlights_status_rule_skips_ambiguous_previous_lep_pages() -> None:
    current = _consistent_document()
    current.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Page 401", "N"),
        ]
    )
    previous = _document(
        [
            _lep_page(
                left=[("Repair", "401", "JUL 66")],
                right=[("Assembly", "401", "JUL 66")],
            )
        ]
    )
    status_rule = next(
        rule for rule in _REVISION_RULES if rule.id == "CUSTOM_REVISION_HIGHLIGHTS_STATUS"
    )

    _results, raws = execute_pdf_rules(
        current,
        [status_rule],
        document=_DOCUMENT,
        previous_revision_pdf=previous,
    )

    assert not any(raw.rule_code == status_rule.id for raw in raws)


def test_invalid_highlights_designation_is_reported_on_its_cell() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "X"),
        ]
    )

    findings = [
        finding
        for finding in _findings(parsed)
        if finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
    ]

    assert len(findings) == 1
    assert findings[0].original == "X"
    assert findings[0].bbox is not None
    assert "R, N, U ou D" in findings[0].message


def test_highlights_page_row_without_designation_is_reported() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", ""),
            ("Avionics", "Pages 403 to 404", "   "),
        ]
    )

    _results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)
    missing = [
        raw
        for raw in raws
        if raw.rule_code == "CUSTOM_HIGHLIGHTS_DESIGNATION_REQUIRED"
    ]

    assert len(missing) == 2
    assert missing[0].page == 1
    assert missing[0].bbox is not None
    assert missing[0].severity == "error"
    assert not any(
        raw.rule_code == "CUSTOM_REVISION_HIGHLIGHTS_STATUS" for raw in raws
    )


def test_deleted_highlights_status_conflicts_with_page_still_in_current_document() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "D"),
        ]
    )

    findings = [
        finding
        for finding in _findings(parsed)
        if finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
    ]

    assert len(findings) == 1
    assert findings[0].original == "D"
    assert findings[0].bbox is not None
    assert "401" in findings[0].message


def test_deleted_status_is_checked_even_without_an_extracted_lep() -> None:
    highlights = _highlights_page(
        [
            ("Repair", "Page 601", "D"),
        ]
    )
    parsed = _document(
        [
            highlights,
            _page(2, _footer(2, "Page 601", "JUL 66")),
        ]
    )

    findings = [
        finding
        for finding in _findings(parsed)
        if finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
    ]

    assert len(findings) == 1
    assert findings[0].original == "D"
    assert "601" in findings[0].message


def test_deleted_status_accepts_blank_lep_entries_without_current_pages() -> None:
    parsed = _document(
        [
            _highlights_page(
                [
                    ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
                    ("List of Approved Repairs", "LAR Page 1 to LAR Page 2", "D"),
                ]
            ),
            _lep_page(
                left=[
                    ("List of Approved Repairs", "LAR 1", "Blank *"),
                    ("", "LAR 2", "Blank *"),
                ],
                right=[],
                page=2,
            ),
        ]
    )

    findings = [
        finding
        for finding in _findings(parsed)
        if finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
    ]

    assert findings == []


def test_deleted_status_accepts_deleted_lep_placeholders_without_current_pages() -> None:
    parsed = _document(
        [
            _highlights_page(
                [
                    ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
                    ("List of Approved Repairs", "LAR Page 1 to LAR Page 2", "D"),
                ]
            ),
            _lep_page(
                left=[
                    ("List of Approved Repairs", "LAR 1", "Deleted *"),
                    ("", "LAR 2", "Deleted *"),
                ],
                right=[],
                page=2,
            ),
        ]
    )

    findings = [
        finding
        for finding in _findings(parsed)
        if finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
    ]

    assert findings == []


def test_highlights_u_matches_unstarred_previous_lep_and_footer_dates() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "U"),
        ]
    )
    parsed.pages[1] = _lep_with(
        ("Repair", "401", "JUL 66"), ("", "402", "JUL 66")
    )
    parsed.pages[2] = _page(3, _footer(3, "Page 401", "JUL 66"))
    parsed.pages[3] = _page(4, _footer(4, "Page 402", "JUL 66"))

    assert not any(
        finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
        for finding in _findings(parsed)
    )


def test_highlights_u_is_not_flagged_when_only_the_lep_star_disagrees() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "U"),
        ]
    )
    parsed.pages[1] = _lep_with(
        ("Repair", "401", "JUL 66 *"), ("", "402", "JUL 66 *")
    )
    parsed.pages[2] = _page(3, _footer(3, "Page 401", "JUL 66"))
    parsed.pages[3] = _page(4, _footer(4, "Page 402", "JUL 66"))

    assert not any(
        finding.control == revision.HIGHLIGHTS_STATUS_CONSISTENCY
        for finding in _findings(parsed)
    )


def test_blank_lep_star_matches_new_status_of_its_odd_page() -> None:
    cases = (
        ("N", "R", "Blank *", []),
        ("N", "R", "Blank", [revision.BLANK_LEP_STAR]),
        ("R", "N", "Blank *", [revision.BLANK_LEP_STAR]),
        ("R", "N", "Blank", []),
    )

    for odd_status, even_status, blank_date, expected_controls in cases:
        parsed = _consistent_document()
        parsed.pages[0] = _highlights_page(
            [
                ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
                ("Repair", "Page  401", odd_status),
                ("", "Page  402", even_status),
            ]
        )
        parsed.pages[1] = _lep_with(
            ("Repair", "401", f"{_REVISION_DATE} *"),
            ("", "402", blank_date),
        )

        findings = _findings(parsed)

        assert [finding.control for finding in findings] == expected_controls
        if expected_controls:
            assert findings[0].original == blank_date
            assert findings[0].proposed == (
                "Blank *" if odd_status == "N" else "Blank"
            )


def test_revised_page_keeping_its_old_lep_date_is_reported() -> None:
    parsed = _consistent_document()
    parsed.pages[1] = _lep_with(
        ("Repair", "401", "JUL 66 *"), ("", "402", f"{_REVISION_DATE} *")
    )

    findings = _findings(parsed)

    assert [finding.control for finding in findings] == [revision.LEP_DATE]
    assert findings[0].proposed == f"{_REVISION_DATE} *"


def test_footer_date_must_match_the_revision_on_a_modified_page() -> None:
    parsed = _consistent_document()
    parsed.pages[2] = _page(3, _footer(3, "Page 401", "JAN 27/26"))

    findings = _findings(parsed)

    assert [finding.control for finding in findings] == [revision.FOOTER_DATE]
    assert (findings[0].page, findings[0].original, findings[0].proposed) == (
        3,
        "JAN 27/26",
        _REVISION_DATE,
    )


def test_footer_page_number_rejects_two_numbers_and_suggests_the_first() -> None:
    parsed = _consistent_document()
    parsed.pages[2] = _page(3, _footer(3, "Page 25/26", _REVISION_DATE))

    findings = [
        finding
        for finding in _findings(parsed)
        if finding.control == revision.FOOTER_PAGE_NUMBER and finding.page == 3
    ]

    assert len(findings) == 1
    assert findings[0].original == "Page 25/26"
    assert findings[0].proposed == "Page 25"
    assert findings[0].bbox is not None


def test_unchanged_page_keeps_its_own_date_in_the_footer() -> None:
    parsed = _consistent_document()
    parsed.pages[4] = _page(5, _footer(5, "Page 501", "JAN 66"))

    findings = _findings(parsed)

    assert [finding.control for finding in findings] == [revision.FOOTER_DATE]
    assert findings[0].proposed == "JUL 66"


def test_unchanged_page_carrying_the_new_date_is_reported_as_undeclared() -> None:
    parsed = _consistent_document()
    parsed.pages[4] = _page(5, _footer(5, "Page 501", _REVISION_DATE))

    findings = _findings(parsed)

    assert [finding.control for finding in findings] == [revision.UNDECLARED_PAGE]


def test_page_absent_from_the_lep_is_reported() -> None:
    parsed = _consistent_document()
    parsed.pages.append(_page(6, _footer(6, "Page 601", "JUL 66")))
    parsed.page_count = 6

    state = _state(parsed)
    findings = [finding for finding in state.findings if finding.control == revision.PAGE_NOT_IN_LEP]

    assert _codes(parsed) == [revision.PAGE_NOT_IN_LEP]
    assert len(findings) == 1
    assert findings[0].bbox == state.footers[-1].label_bbox


def test_lep_page_ids_fused_with_subject_spans_are_still_extracted() -> None:
    page = _lep_page(
        left=[
            ("Trouble Shooting", "801", "AUG 30/75"),
            ("", "802", "AUG 30/75"),
            ("Special Equipment", "1001", "JUL 30/26 *"),
            ("and Tooling", "1002", "AUG 30/75"),
        ],
        right=[],
        page=2,
    )
    merged_ids = {"Trouble Shooting": "801", "Special Equipment": "1001"}
    spans = []
    for span in page.spans:
        if span.text in merged_ids:
            spans.append(
                _span(
                    f"{span.text} {merged_ids[span.text]}",
                    span.bbox[0],
                    (span.bbox[1] + span.bbox[3]) / 2,
                    page.page,
                )
            )
        elif span.text not in merged_ids.values():
            spans.append(span)
    page.spans = spans
    page.text = "\n".join(span.text for span in spans)

    entries, _subject = revision.extract_lep(page)
    subject_by_page = {entry.page_key: entry.subject for entry in entries}

    assert subject_by_page["801"] == "Trouble Shooting"
    assert subject_by_page["802"] == "Trouble Shooting"
    assert subject_by_page["1001"] == "Special Equipment"
    assert subject_by_page["1002"] == "Special Equipment and Tooling"


def test_ambiguous_page_number_listed_in_lep_is_not_reported_absent() -> None:
    date = revision.parse_date("JUL 66")
    assert date is not None
    state = revision.RevisionState(
        revision_date=revision.parse_date(_REVISION_DATE),
        full_document=True,
        lep=[
            revision.LepEntry(
                subject="Description and Operation",
                page_key="1",
                date=date,
                date_text="JUL 66",
                is_blank=False,
                starred=False,
                page=9,
                bbox=(0.0, 0.0, 100.0, 10.0),
            ),
            revision.LepEntry(
                subject="Illustrated Parts List",
                page_key="1",
                date=date,
                date_text="JUL 66",
                is_blank=False,
                starred=False,
                page=10,
                bbox=(0.0, 0.0, 100.0, 10.0),
            ),
        ],
        footers=[
            revision.PageFooter(
                page=19,
                page_key="1",
                observed_page_key="1",
                label_text="Page 1",
                label_bbox=(0.0, 0.0, 100.0, 10.0),
                page_number_bbox=(0.0, 0.0, 100.0, 10.0),
                date=date,
                date_text="JUL 66",
                date_bbox=(0.0, 10.0, 100.0, 20.0),
            )
        ],
    )

    assert revision._footer_findings(state) == []


def test_a_partial_page_range_silences_the_absence_controls() -> None:
    full = _consistent_document()
    partial = ParsedPdf(
        page_count=full.page_count,
        pages=full.pages[:4] + [_page(6, _footer(6, "Page 601", "JUL 66"))],
        full_text=full.full_text,
        is_signed=False,
    )

    assert _codes(partial) == []


def test_highlights_must_declare_pages_by_odd_even_pair() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Page  401", "R"),
        ]
    )
    parsed.pages[1] = _lep_with(
        ("Repair", "401", f"{_REVISION_DATE} *"), ("", "402", "JUL 66")
    )
    parsed.pages[3] = _page(4, _footer(4, "Page 402", "JUL 66"))

    findings = _findings(parsed)

    assert [finding.control for finding in findings] == [revision.HIGHLIGHTS_PAIRING]
    assert "402" in findings[0].message


def test_highlights_pairing_accepts_compound_intro_odd_even_range() -> None:
    page = _highlights_page(
        [("Illustrated Parts List", "INTRO 1101 Page 3 to INTRO Page 4", "R")]
    )
    entries = revision.extract_highlights(page)
    state = revision.RevisionState(highlights=entries)

    assert entries[0].page_keys == ("INTRO 1101 3", "INTRO 1101 4")
    assert revision._pairing_findings(state) == []


def test_highlights_pairing_reports_blank_lep_partner_omitted_from_highlights() -> None:
    state = revision.RevisionState(
        highlights=[
            revision.HighlightsEntry(
                subject="List of Materials",
                pages_text="LM Page 1",
                page_keys=("LM 1",),
                status="R",
                page=1,
                bbox=(0.0, 0.0, 100.0, 10.0),
                status_bbox=(100.0, 0.0, 110.0, 10.0),
            )
        ],
        lep=[
            revision.LepEntry(
                subject="List of Materials",
                page_key="LM 2",
                date=None,
                date_text="Blank *",
                is_blank=True,
                starred=True,
                page=9,
                bbox=(0.0, 0.0, 100.0, 10.0),
            )
        ],
    )

    findings = revision._pairing_findings(state)

    assert len(findings) == 1
    assert findings[0].control == revision.HIGHLIGHTS_PAIRING
    assert "LM 2" in findings[0].message


def test_highlights_page_label_wording_and_alignment() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Page 401 to 402", "R"),
        ]
    )

    findings = _findings(parsed)

    assert [finding.control for finding in findings] == [revision.HIGHLIGHTS_PAGE_LABEL]
    assert findings[0].proposed == "Pages 401 to 402"


def test_single_page_highlights_label_passes_when_number_is_visually_aligned() -> None:
    page = _highlights_page(
        [
            ("Repair", "Page 1001", "R"),
            ("Repair", "Page  1002", "R"),
            ("Illustrated Parts List", "Pages 1101-1 to 1101-2", "R"),
        ]
    )
    page.words = [
        _word("Page", 90.7, 264.0, 0),
        _word("1001", 126.7, 264.0, 1),
        _word("Page", 90.7, 306.0, 2),
        _word("1002", 126.7, 306.0, 3),
        _word("Pages", 90.7, 348.0, 4),
        _word("1101-1", 126.7, 348.0, 5),
        _word("to", 168.7, 348.0, 6),
        _word("1101-2", 180.7, 348.0, 7),
    ]

    entries = revision.extract_highlights(page)
    state = revision.RevisionState(highlights=entries)

    assert entries[0].page_number_x == 126.7
    assert revision._page_label_findings(state) == []


def test_single_page_label_requires_two_spaces() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Page 401", "R"),
            ("Repair", "Page  402", "R"),
        ]
    )

    findings = _findings(parsed)

    assert [finding.control for finding in findings] == [revision.HIGHLIGHTS_PAGE_LABEL]
    assert findings[0].proposed == "Page  401"


def test_revised_page_without_footer_number_is_reported() -> None:
    parsed = _consistent_document()
    parsed.pages[3] = _page(4, [_span("no footer", 90.0, 300.0, 4)])

    assert _codes(parsed) == [revision.FOOTER_PAGE_NUMBER]


def test_compiled_rules_emit_one_suggestion_per_divergence() -> None:
    parsed = _consistent_document()
    parsed.pages[2] = _page(3, _footer(3, "Page 401", "JAN 27/26"))

    results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)

    failed = {result.rule_id for result in results if result.status == "FAIL"}
    assert failed == {"CUSTOM_REVISION_FOOTER_DATE"}
    assert {result.rule_id for result in results} == {rule.id for rule in _REVISION_RULES}
    assert [(raw.rule_code, raw.page, raw.original, raw.proposed) for raw in raws] == [
        ("CUSTOM_REVISION_FOOTER_DATE", 3, "JAN 27/26", _REVISION_DATE)
    ]
    assert raws[0].severity == "error"
    assert raws[0].bbox is not None


def test_a_disabled_revision_rule_simply_does_not_run() -> None:
    parsed = _consistent_document()
    parsed.pages[2] = _page(3, _footer(3, "Page 401", "JAN 27/26"))
    enabled = [
        rule for rule in _REVISION_RULES if rule.id != "CUSTOM_REVISION_FOOTER_DATE"
    ]

    results, raws = execute_pdf_rules(parsed, enabled, document=_DOCUMENT)

    assert raws == []
    assert all(result.status == "PASS" for result in results)


def test_revision_rules_are_skipped_without_a_revision_date() -> None:
    parsed = _consistent_document()
    parsed.pages[2] = _page(3, _footer(3, "Page 401", "JAN 27/26"))

    results, raws = execute_pdf_rules(
        parsed, _REVISION_RULES, document=SimpleNamespace(meta_revision_date=None)
    )

    assert (results, raws) == ([], [])


def test_rules_pass_without_highlights_or_lep() -> None:
    parsed = _document([_page(1, _footer(1, "Page 401", _REVISION_DATE))])

    results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)

    assert raws == []
    assert {result.status for result in results} == {"PASS"}
    assert [page.is_modified for page in parsed.pages] == [None]


def test_classify_pages_marks_modified_pages_before_the_other_rules() -> None:
    parsed = _consistent_document()

    classify_pages(parsed, _DOCUMENT)

    assert [page.is_modified for page in parsed.pages] == [True, True, True, True, False]
