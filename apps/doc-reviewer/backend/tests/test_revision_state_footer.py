"""Revision state: footer page number and date rules."""

from __future__ import annotations

from types import SimpleNamespace

from app.checks.thales_rules.ata100 import revision_engine as revision
from app.parsers.pdf_parser import (
    ParsedPage,
    Span,
)
from tests.helpers.revision_state import (
    _COPYRIGHT,
    _DOCUMENT,
    _REVISION_DATE,
    _REVISION_RULES,
    _codes,
    _consistent_document,
    _findings,
    _footer,
    _highlights_page,
    _lep_page,
    _lep_with,
    _page,
    _span,
    _state,
    execute_pdf_rules,
)


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
    from app.checks.thales_rules.ata100 import operations
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


def test_boeing_revision_section_footers_use_boeing_page_labels() -> None:
    parsed = _consistent_document()
    parsed.pages.append(
        _page(
            6,
            [_span("RECORD OF REVISIONS", 100.0, 120.0, 6)]
            + _footer(6, "ROR Page 1", _REVISION_DATE),
        )
    )
    parsed.page_count = 6
    document = SimpleNamespace(
        meta_revision_date=_REVISION_DATE,
        meta_first_issue_date="JUL 1966",
        meta_last_issue_date="MAR 77",
        meta_manufacturer="Boeing",
    )

    findings = [
        finding
        for finding in _findings(parsed, document)
        if finding.control == revision.FOOTER_PAGE_NUMBER
    ]

    assert {(finding.page, finding.proposed) for finding in findings} == {
        (2, "LEP-1"),
        (6, "RR-1"),
    }


def test_boeing_revision_section_footers_accept_boeing_page_labels() -> None:
    parsed = _consistent_document()
    for span in parsed.pages[1].spans:
        if span.text == "LEP Page 1":
            span.text = "Page LEP-1"
    parsed.pages[1].text = "\n".join(span.text for span in parsed.pages[1].spans)
    parsed.pages.append(
        _page(
            6,
            [_span("RECORD OF REVISIONS", 100.0, 120.0, 6)]
            + _footer(6, "Page RR-1", _REVISION_DATE),
        )
    )
    parsed.page_count = 6
    document = SimpleNamespace(
        meta_revision_date=_REVISION_DATE,
        meta_first_issue_date="JUL 1966",
        meta_last_issue_date="MAR 77",
        meta_manufacturer="Boeing",
    )

    findings = [
        finding
        for finding in _findings(parsed, document)
        if finding.control == revision.FOOTER_PAGE_NUMBER
    ]

    assert not any(finding.page in {2, 6} for finding in findings)


def test_boeing_revision_section_footers_suggest_boeing_page_labels() -> None:
    parsed = _consistent_document()
    parsed.pages.append(
        _page(
            6,
            [_span("RECORD OF REVISIONS", 100.0, 120.0, 6)]
            + _footer(6, "ROR Page 1", _REVISION_DATE),
        )
    )
    parsed.page_count = 6
    document = SimpleNamespace(
        meta_revision_date=_REVISION_DATE,
        meta_first_issue_date="JUL 1966",
        meta_last_issue_date="MAR 77",
        meta_manufacturer="Boeing",
    )

    findings = [
        finding
        for finding in _findings(parsed, document)
        if finding.control == revision.FOOTER_PAGE_NUMBER
    ]

    assert {(finding.page, finding.proposed) for finding in findings} == {
        (2, "LEP-1"),
        (6, "RR-1"),
    }


def test_unchanged_revision_evidence_downgrades_linked_star_and_footer_dates() -> None:
    parsed = _consistent_document()
    parsed.pages[0] = _highlights_page(
        [
            ("List of Effective Pages", "LEP Page 1 to LEP Page 2", "N"),
            ("Repair", "Pages 401 to 402", "R"),
        ]
    )
    parsed.pages[1] = _lep_with(
        ("Repair", "401", "JUL 66"),
        ("", "402", "JUL 66"),
    )
    parsed.pages[2] = _page(3, _footer(3, "Page 401", "JUL 66"))
    parsed.pages[3] = _page(4, _footer(4, "Page 402", "JUL 66"))

    _results, raws = execute_pdf_rules(parsed, _REVISION_RULES, document=_DOCUMENT)
    linked = [
        raw
        for raw in raws
        if raw.rule_code in {
            "CUSTOM_REVISION_LEP_STAR",
            "CUSTOM_REVISION_FOOTER_DATE",
        }
    ]

    assert len(linked) == 4
    assert all(raw.severity == "info" for raw in linked)
    assert all(raw.proposed == "" for raw in linked)
    assert all("CUSTOM_REVISION_HIGHLIGHTS_STATUS" in raw.message for raw in linked)


def test_wrong_known_section_footer_number_does_not_report_page_as_absent() -> None:
    parsed = _consistent_document()
    lep_page = parsed.pages[1]
    for span in lep_page.spans:
        if span.text == "LEP Page 1":
            span.text = "LEP Page 99"
    lep_page.text = "\n".join(span.text for span in lep_page.spans)

    findings = _findings(parsed)

    assert any(
        finding.control == revision.FOOTER_PAGE_NUMBER
        and finding.page == 2
        and finding.proposed == "LEP Page 1"
        for finding in findings
    )
    assert not any(
        finding.control == revision.PAGE_NOT_IN_LEP and finding.page == 2
        for finding in findings
    )
    assert revision.MODIFIED_PAGE_ABSENT not in _codes(parsed)


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


def test_highlights_footer_date_must_match_the_revision() -> None:
    parsed = _consistent_document()
    highlights_page = parsed.pages[0]
    for span in highlights_page.spans:
        if span.text == _REVISION_DATE:
            span.text = "JAN 27/26"
    highlights_page.text = "\n".join(span.text for span in highlights_page.spans)

    findings = _findings(parsed)

    assert [
        (finding.control, finding.page, finding.original, finding.proposed)
        for finding in findings
    ] == [(revision.FOOTER_DATE, 1, "JAN 27/26", _REVISION_DATE)]


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


def test_revised_page_without_footer_number_is_reported() -> None:
    parsed = _consistent_document()
    parsed.pages[3] = _page(4, [_span("no footer", 90.0, 300.0, 4)])

    assert _codes(parsed) == [revision.FOOTER_PAGE_NUMBER]
