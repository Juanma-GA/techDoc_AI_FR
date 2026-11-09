"""Revision state: extraction and detection of the Highlights, LEP, ROR and footer sources."""

from __future__ import annotations

import pytest

from app.checks.thales_rules.ata100 import revision_engine as revision
from app.parsers.pdf_parser import (
    ParsedPage,
    Span,
)
from tests.helpers.revision_state import (
    _COPYRIGHT,
    _DOCUMENT,
    _REVISION_DATE,
    _codes,
    _consistent_document,
    _document,
    _findings,
    _footer,
    _highlights_page,
    _lep_page,
    _lep_with,
    _page,
    _span,
    _state,
    _word,
)


def test_page_key_normalization_unifies_the_three_sources() -> None:
    assert revision.normalize_page_key("ROR Page 1") == "ROR 1"
    assert revision.normalize_page_key("RR-1") == "ROR 1"
    assert revision.normalize_page_key("LEP-1") == "LEP 1"
    assert revision.normalize_page_key("Page RR-1") == "ROR 1"
    assert revision.normalize_page_key("Page LEP-1") == "LEP 1"
    assert revision.normalize_page_key("INTRO-1") == "INTRO 1"
    assert revision.normalize_page_key("TC-1") == "TC 1"
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
    ) == ("1101 1", "1102 2")
    assert revision.expand_page_range("Page  1101-1") == ("1101 1",)


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


def test_highlights_header_uses_word_geometry_when_column_titles_are_merged() -> None:
    page = _page(
        1,
        [
            _span("Chapter/Section and Page No", 54.0, 100.0, 1),
            _span("Designation Description of Change", 254.6, 100.0, 1),
            _span("Page 701", 90.7, 120.0, 1),
            _span("R", 285.4, 120.0, 1),
            _span("Consumable and minor corrections", 329.0, 120.0, 1),
        ],
    )
    page.words = [
        _word("Designation", 254.6, 100.0, 0),
        _word("Description", 329.2, 100.0, 1),
        _word("of", 401.2, 100.0, 2),
        _word("Change", 419.2, 100.0, 3),
    ]

    entries = revision.extract_highlights(page)

    assert len(entries) == 1
    assert entries[0].page_keys == ("701",)
    assert entries[0].status == "R"


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


def test_highlights_keeps_chapter_and_page_pair_across_missing_designation() -> None:
    page = _page(
        1,
        [
            _span("Chapter/Section and Page No", 54.0, 100.0, 1),
            _span("Designation", 285.0, 100.0, 1),
            _span("Description of Change", 366.0, 100.0, 1),
            _span("Assembly", 90.7, 120.0, 1),
            _span("Page 701", 90.7, 140.0, 1),
            _span("R", 322.2, 140.0, 1),
            _span("Consumables and Standard Practices", 366.0, 140.0, 1),
            _span("Manual updated.", 366.0, 154.0, 1),
            _span("Page 702", 90.7, 180.0, 1),
            _span("Page 705", 90.7, 220.0, 1),
            _span("U", 322.2, 220.0, 1),
            _span("Page 706", 90.7, 240.0, 1),
            _span("R", 322.2, 240.0, 1),
            _span("Updated.", 366.0, 240.0, 1),
        ],
    )

    entries = revision.extract_highlights(page)
    state = revision.RevisionState(highlights=entries)

    assert [entry.page_keys for entry in entries] == [("701",), ("702",), ("705",), ("706",)]
    assert [entry.subject for entry in entries] == ["Assembly"] * 4
    assert [entry.status for entry in entries] == ["R", "", "U", "R"]
    assert entries[0].description == "Consumables and Standard Practices Manual updated."
    assert revision._pairing_findings(state) == []
    assert revision._highlights_chapter_findings(state) == []
    missing = revision.extract_missing_highlights_designations(page)
    assert [entry.page_keys for entry in missing] == [("702",)]


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


def test_hyphenated_highlights_pages_match_numbered_lep_pages() -> None:
    highlights_page = _highlights_page(
        [("Illustrated Parts List", "Pages 1101-1 to 1101-2", "R")]
    )
    lep_page = _lep_page(
        left=[
            ("", "1101 1", f"{_REVISION_DATE} *"),
            ("", "1102 2", f"{_REVISION_DATE} *"),
        ],
        right=[],
        page=2,
    )
    highlights = revision.extract_highlights(highlights_page)
    lep, _subject = revision.extract_lep(lep_page)
    state = revision.RevisionState(highlights=highlights, lep=lep)

    assert highlights[0].page_keys == ("1101 1", "1102 2")
    assert [state.highlights_status_for_lep(entry) for entry in lep] == ["R", "R"]
    assert revision._pairing_findings(state) == []


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


@pytest.mark.parametrize(
    "title",
    [
        "LIST OF EFFECTIVES PAGES",
        "LIST OF EFECTIVE PAGES",
        "LSIT OF EFFECTIVE PAGES",
        "LIST OF EFFETCIVE PAGES",
        "LIST OF EFFECTIVE PAGS",
        "LIST OF EFECTIVES PAGS",
        "List of effective pages:",
        "LIST OF EFFECTIVE\nPAGES",
        "LISTOFEFFECTIVEPAGES",
    ],
)
def test_lep_detection_tolerates_title_typos_with_table_structure(title: str) -> None:
    parsed = _consistent_document()
    page = parsed.pages[1]
    page.spans[0].text = title
    for span in page.spans:
        span.text = span.text.replace("LEP Page 1", "Page 401")
    page.text = "\n".join(span.text for span in page.spans)

    state = _state(parsed)

    assert state.lep_pages == (2,)
    assert state.available
    assert parsed.pages[2].is_modified is True
    assert parsed.pages[4].is_modified is False


def test_lep_detection_uses_table_and_footer_when_title_is_unreadable() -> None:
    page = _lep_with(("Repair", "401", f"{_REVISION_DATE} *"))
    page.spans[0].text = "Unreadable heading"
    page.text = "\n".join(span.text for span in page.spans)

    assert revision._is_lep_page(page)


@pytest.mark.parametrize("title", ["LIST OF MATERIALS", "RECORD OF REVISIONS"])
def test_lep_detection_rejects_other_tables(title: str) -> None:
    page = _lep_with(("Repair", "401", f"{_REVISION_DATE} *"))
    page.spans[0].text = title
    for span in page.spans:
        span.text = span.text.replace("LEP Page 1", "Page 401")
    page.text = "\n".join(span.text for span in page.spans)

    assert not revision._is_lep_page(page)


def test_lep_detection_rejects_fuzzy_title_without_table() -> None:
    page = _page(1, [_span("LIST OF EFFECTIVES PAGES", 100.0, 100.0, 1)])

    assert not revision._is_lep_page(page)


def test_lep_detection_rejects_highlights_mention() -> None:
    page = _highlights_page(
        [("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N")]
    )

    assert not revision._is_lep_page(page)


@pytest.mark.parametrize(
    ("highlights_pages", "lep_subject"),
    [
        ("Intro Page 1", "Introduction"),
        ("TC page 1", "Table of Contents"),
        ("TP page 1", "Title Page"),
    ],
)
def test_lep_star_matches_intro_and_section_aliases(
    highlights_pages: str,
    lep_subject: str,
) -> None:
    revision_date = revision.parse_date(_REVISION_DATE)
    assert revision_date is not None
    highlights = revision.HighlightsEntry(
        subject="Introduction",
        pages_text=highlights_pages,
        page_keys=revision.expand_page_range(highlights_pages),
        status="R",
        page=1,
        bbox=(0.0, 0.0, 1.0, 1.0),
        status_bbox=(0.0, 0.0, 1.0, 1.0),
    )
    lep_entry = revision.LepEntry(
        subject=lep_subject,
        page_key="1",
        date=revision_date,
        date_text=_REVISION_DATE,
        is_blank=False,
        starred=False,
        page=2,
        bbox=(0.0, 0.0, 1.0, 1.0),
    )
    state = revision.RevisionState(
        revision_date=revision_date,
        highlights=[highlights],
        lep=[lep_entry],
    )

    findings = revision._lep_findings(state)

    assert revision.LEP_STAR in [finding.control for finding in findings]


def test_table_of_contents_status_does_not_contaminate_title_page_status() -> None:
    revision_date = revision.parse_date(_REVISION_DATE)
    assert revision_date is not None
    highlights = [
        revision.HighlightsEntry(
            subject="Table of Contents",
            pages_text="TC Page 1 to TC Page 2",
            page_keys=revision.expand_page_range("TC Page 1 to TC Page 2"),
            status="R",
            page=1,
            bbox=(0.0, 0.0, 1.0, 1.0),
            status_bbox=(0.0, 0.0, 1.0, 1.0),
        ),
        revision.HighlightsEntry(
            subject="Title Page",
            pages_text="TP 2",
            page_keys=revision.expand_page_range("TP 2"),
            status="N",
            page=1,
            bbox=(0.0, 0.0, 1.0, 1.0),
            status_bbox=(0.0, 0.0, 1.0, 1.0),
        ),
    ]
    title_page = revision.LepEntry(
        subject="Title Page",
        page_key="TP 2",
        date=revision_date,
        date_text=f"{_REVISION_DATE} *",
        is_blank=False,
        starred=True,
        page=2,
        bbox=(0.0, 0.0, 1.0, 1.0),
    )
    state = revision.RevisionState(
        revision_date=revision_date,
        highlights=highlights,
        lep=[title_page],
    )

    assert state.highlights_status_for_lep(title_page, "TP 2") == "N"


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


def test_highlights_extraction_does_not_merge_subject_across_page_row() -> None:
    spans = [
        Span("Chapter/Section and Page No", (69.8, 179.9, 231.8, 194.1), 1, "Arial", 10.0),
        Span("Designation", (255.4, 179.9, 321.4, 194.1), 1, "Arial", 10.0),
        Span("Description of Change", (363.5, 179.9, 489.5, 194.1), 1, "Arial", 10.0),
        Span("Testing", (54.0, 194.6, 96.0, 208.8), 1, "Arial", 10.0),
        Span("Pages 701 to 702 ", (54.0, 208.7, 156.0, 222.9), 1, "Arial", 10.0),
        Span("Environmental conditions and ", (329.0, 208.7, 500.2, 222.9), 1, "Arial", 10.0),
        Span("minor technical correction added.", (329.0, 222.9, 511.1, 237.1), 1, "Arial", 10.0),
        Span("Storage Instructions", (54.0, 251.2, 174.0, 265.4), 1, "Arial", 10.0),
        Span("Page  901 ", (54.0, 265.4, 114.0, 279.6), 1, "Arial", 10.0),
        Span("R ", (285.5, 265.4, 297.5, 279.6), 1, "Arial", 10.0),
        Span("Environmental conditions and ", (329.0, 265.4, 500.2, 279.6), 1, "Arial", 10.0),
    ]
    highlights_page = ParsedPage(
        page=1,
        text="\n".join(span.text for span in spans),
        spans=spans,
        page_type="HIGHLIGHTS_PAGE_1",
    )
    entries = revision.extract_highlights(highlights_page)

    assert [
        (entry.subject, entry.pages_text, entry.status)
        for entry in entries
    ] == [
        ("Testing", "Pages 701 to 702", ""),
        ("Storage Instructions", "Page  901", "R"),
    ]


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
