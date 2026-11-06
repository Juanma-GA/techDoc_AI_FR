"""Revision state: page modified / unchanged decision and compiled rule wiring."""

from __future__ import annotations

from types import SimpleNamespace

from app.checks.thales_rules.ata100.page_classifier import classify_pages
from tests.helpers.revision_state import (
    _DOCUMENT,
    _REVISION_DATE,
    _REVISION_RULES,
    _codes,
    _consistent_document,
    _document,
    _footer,
    _highlights_page,
    _lep_page,
    _lep_with,
    _page,
    _ror_page,
    _span,
    _state,
    execute_pdf_rules,
)


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


def test_all_highlights_pages_are_forced_modified_and_unmatched_pages_default_unchanged() -> None:
    parsed = _consistent_document()
    second_highlights = _highlights_page([], page=2)
    for span in second_highlights.spans:
        if span.text == "Highlights Page 1":
            span.text = "Highlights Page 2"
    second_highlights.text = "\n".join(span.text for span in second_highlights.spans)
    parsed.pages.insert(1, second_highlights)
    third_highlights = _highlights_page([], page=3)
    for span in third_highlights.spans:
        if span.text == "Highlights Page 1":
            span.text = "Highlights Page 3"
    third_highlights.text = "\n".join(span.text for span in third_highlights.spans)
    parsed.pages.insert(2, third_highlights)
    parsed.pages.append(_page(8, _footer(8, "Page 999", "JUL 66")))
    for page_number, page in enumerate(parsed.pages, start=1):
        page.page = page_number
        for span in page.spans:
            span.page = page_number
    parsed.page_count = len(parsed.pages)

    state = _state(parsed)

    assert state.available is True
    assert [page.is_modified for page in parsed.pages[:3]] == [True, True, True]
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


def test_compiled_rules_emit_one_suggestion_per_divergence() -> None:
    parsed = _consistent_document()
    parsed.pages[0].page_type = "HIGHLIGHTS_PAGE_1"
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
