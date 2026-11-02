"""Revision state: LEP star, Highlights status, designation, deleted pages and pairing rules."""

from __future__ import annotations

import pytest

from app.checks.thales_rules.ata100 import revision_engine as revision
from app.parsers.pdf_parser import ParsedPdf
from tests.helpers.revision_state import (
    _DOCUMENT,
    _REVISION_DATE,
    _REVISION_RULES,
    _codes,
    _consistent_document,
    _document,
    _findings,
    _footer,
    _highlights_page,
    _lep_page,
    _lep_with,
    _page,
    _state,
    _word,
    execute_pdf_rules,
)


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


def test_star_with_missing_highlights_designation_is_informational() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", ""),
        ]
    )
    parsed.pages[1] = _lep_with(
        ("Repair", "401", f"{_REVISION_DATE} *"),
        ("", "402", _REVISION_DATE),
    )

    _results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)
    star = next(
        raw
        for raw in raws
        if raw.rule_code == "CUSTOM_REVISION_UNDECLARED_STAR"
        and "page 401" in raw.message
    )

    assert star.severity == "info"
    assert star.proposed == ""
    assert "CUSTOM_HIGHLIGHTS_DESIGNATION_REQUIRED" in star.message
    assert "peut être justifiée" in star.message


def test_missing_highlights_designation_on_another_page_does_not_downgrade_star() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Other", "Page 999", ""),
        ]
    )
    parsed.pages[1] = _lep_with(
        ("Repair", "401", f"{_REVISION_DATE} *"),
        ("", "402", _REVISION_DATE),
    )

    _results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)
    star = next(
        raw
        for raw in raws
        if raw.rule_code == "CUSTOM_REVISION_UNDECLARED_STAR"
        and "page 401" in raw.message
    )

    assert star.severity == "error"
    assert star.proposed == _REVISION_DATE
    assert "CUSTOM_HIGHLIGHTS_DESIGNATION_REQUIRED" not in star.message


def test_star_with_invalid_highlights_designation_is_informational() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "X"),
        ]
    )

    _results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)
    star = next(
        raw
        for raw in raws
        if raw.rule_code == "CUSTOM_REVISION_UNDECLARED_STAR"
        and "page 401" in raw.message
    )

    assert star.severity == "info"
    assert star.proposed == ""
    assert "CUSTOM_REVISION_HIGHLIGHTS_STATUS" in star.message
    assert "invalide" in star.message


def test_star_conflicting_with_unchanged_highlights_is_informational() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "U"),
        ]
    )

    _results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)
    star = next(
        raw
        for raw in raws
        if raw.rule_code == "CUSTOM_REVISION_UNDECLARED_STAR"
        and "page 401" in raw.message
    )

    assert star.severity == "info"
    assert star.proposed == ""
    assert "CUSTOM_REVISION_HIGHLIGHTS_STATUS" in star.message


def test_undeclared_page_mentions_invalid_designation_without_downgrading() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "X"),
        ]
    )
    parsed.pages[1] = _lep_with(
        ("Repair", "401", _REVISION_DATE),
        ("", "402", f"{_REVISION_DATE} *"),
    )

    _results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)
    undeclared = next(
        raw
        for raw in raws
        if raw.rule_code == "CUSTOM_REVISION_UNDECLARED_PAGE"
        and "page 401" in raw.message
    )

    assert undeclared.severity == "error"
    assert "CUSTOM_REVISION_HIGHLIGHTS_STATUS" in undeclared.message
    assert "invalide" in undeclared.message
    assert "indice indépendant" in undeclared.message


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


@pytest.mark.parametrize(
    "chapter",
    [
        "Assembly",
        "Assembly and Storage",
        "Assembly Including Storage",
        "Assembly (Including Storage)",
        "Check",
        "Cleaning",
        "Description and Operation",
        "Disassembly",
        "Environmental conditions",
        "Fault Isolation",
        "Illustrated Parts List",
        "Introduction",
        "List of Effective Pages",
        "List of Illustrations",
        "List of Materials",
        "Record of Revisions",
        "Record of Temporary Revisions",
        "Removal Procedure and Special",
        "Repair",
        "Service Bulletin List",
        "Special Tools, Fixtures and Equipment",
        "Special Tools, Fixtures, Equipment and Consumables",
        "Special Tools, Fixtures and Equipment - List of Special Materials",
        "Storage - Packaging - Conditioning",
        "Storage",
        "Table of Contents",
        "Testing",
        "Testing and Fault Isolation",
        "Testing and Trouble Shooting",
        "Test Run",
        "Title Page",
        "Vendor Code List",
        "Illustrated Part Lis",
        "Illustrated part list",
        "Illustarted Parts List",
        "Assebmly",
        "Testng and Fault Isolaton",
        "Specal Tools, Fixtures and Equipmnt",
        "Repa ir",
        "Reapir",
        "Chekc",
    ],
)
def test_highlights_chapter_rule_accepts_catalog_titles(chapter: str) -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            (chapter, "Pages 401 to 402", "R"),
        ]
    )
    parsed.pages[0].page_type = "HIGHLIGHTS_PAGE_1"
    rule = next(
        item for item in _REVISION_RULES if item.id == "CUSTOM_HIGHLIGHTS_CHAPTER"
    )

    results, suggestions = execute_pdf_rules(
        parsed,
        [rule],
        document=_DOCUMENT,
    )

    assert results[0].status == "PASS"
    assert suggestions == []


@pytest.mark.parametrize(
    "chapter",
    [
        "Avionics",
        "Warranty Conditions",
        "Environmental condition",
        "Environmentel conditions",
    ],
)
def test_highlights_chapter_rule_reports_unlisted_title_on_its_cell(chapter: str) -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            (chapter, "Pages 401 to 402", "R"),
        ]
    )
    parsed.pages[0].page_type = "HIGHLIGHTS_PAGE_1"
    rule = next(
        item for item in _REVISION_RULES if item.id == "CUSTOM_HIGHLIGHTS_CHAPTER"
    )

    results, suggestions = execute_pdf_rules(
        parsed,
        [rule],
        document=_DOCUMENT,
    )
    finding = next(item for item in suggestions if item.rule_code == rule.id)
    subject_bbox = revision.extract_highlights(parsed.pages[0])[-1].subject_bbox

    assert results[0].status == "FAIL"
    assert finding.original == chapter
    assert finding.proposed == ""
    assert finding.bbox == subject_bbox


def test_highlights_chapter_rule_ignores_case_and_repeated_spaces() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("aSSEMBLY   and Storage", "Pages 401 to 402", "R"),
        ]
    )
    parsed.pages[0].page_type = "HIGHLIGHTS_PAGE_1"
    rule = next(
        item for item in _REVISION_RULES if item.id == "CUSTOM_HIGHLIGHTS_CHAPTER"
    )

    results, suggestions = execute_pdf_rules(
        parsed,
        [rule],
        document=_DOCUMENT,
    )

    assert results[0].status == "PASS"
    assert suggestions == []


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


def test_page_absent_from_the_lep_is_reported() -> None:
    parsed = _consistent_document()
    parsed.pages.append(_page(6, _footer(6, "Page 601", "JUL 66")))
    parsed.page_count = 6

    state = _state(parsed)
    findings = [finding for finding in state.findings if finding.control == revision.PAGE_NOT_IN_LEP]

    assert _codes(parsed) == [revision.PAGE_NOT_IN_LEP]
    assert len(findings) == 1
    assert findings[0].bbox == state.footers[-1].label_bbox


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
