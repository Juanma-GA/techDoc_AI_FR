"""Cross-source detection of the pages a THALES revision modified."""

from __future__ import annotations

from types import SimpleNamespace

from app.checks.standards import _thales_revision as revision
from app.checks.standards.thales_custom import _REVISION_RULES, classify_pages
from app.core.compiled_rule_executor import execute_pdf_rules
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, Span


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


def _state(parsed: ParsedPdf) -> revision.RevisionState:
    return revision.build_revision_state(parsed, _DOCUMENT)


def _findings(parsed: ParsedPdf) -> list[revision.RevisionFinding]:
    return _state(parsed).findings


def _codes(parsed: ParsedPdf) -> list[str]:
    return [finding.control for finding in _findings(parsed)]


def test_page_key_normalization_unifies_the_three_sources() -> None:
    assert revision.normalize_page_key("ROR Page 1") == "ROR 1"
    assert revision.normalize_page_key("Page 401") == "401"
    assert revision.normalize_page_key("TP 1") == "TP 1"
    assert revision.expand_page_range("Pages 701 to 704") == ("701", "702", "703", "704")
    assert revision.expand_page_range("TP 1 to TP 2") == ("TP 1", "TP 2")
    assert revision.expand_page_range("ROR Page 1 to ROR Page 2") == ("ROR 1", "ROR 2")


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
    assert revision.parse_date("JUL 1966").same_as(revision.parse_date("JUL 66"))
    assert not revision.parse_date("JUL 27/26").same_as(revision.parse_date("JUL 66"))
    assert revision.parse_date("JUL 27/26").sort_key > revision.parse_date("MAR 77").sort_key


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
    assert [page.is_modified for page in parsed.pages] == [None, True, True, True, False]


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

    assert _codes(parsed) == [revision.PAGE_NOT_IN_LEP]


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


def test_revised_page_missing_from_the_document_is_reported() -> None:
    parsed = _consistent_document()
    parsed.pages[3] = _page(4, [_span("no footer", 90.0, 300.0, 4)])

    assert _codes(parsed) == [revision.MODIFIED_PAGE_ABSENT]


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

    assert [page.is_modified for page in parsed.pages] == [None, True, True, True, False]
