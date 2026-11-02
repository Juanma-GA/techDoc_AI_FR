"""Revision state: record of revisions (ROR) detection and date rules."""

from __future__ import annotations

from types import SimpleNamespace

from app.checks.thales_rules.ata100 import revision_engine as revision
from tests.helpers.revision_state import (
    _REVISION_DATE,
    _codes,
    _document,
    _findings,
    _page,
    _ror_page,
    _span,
)


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


def test_ror_insertion_date_only_checks_the_last_table_row() -> None:
    spans = [
        _span("RECORD OF REVISIONS", 100.0, 100.0, 1),
        _span("REVISION DATE", 200.0, 140.0, 1),
        _span("INSERTION DATE", 350.0, 140.0, 1),
        _span("DEC 15/20", 200.0, 170.0, 1),
        _span("FEB 21", 350.0, 170.0, 1),
        _span("JUL 27/26", 200.0, 190.0, 1),
        _span("AUG 26", 350.0, 190.0, 1),
    ]
    document = SimpleNamespace(
        meta_revision_date="JUL 27/26",
        meta_first_issue_date="JUL 1966",
        meta_last_issue_date="MAR 77",
    )

    assert _codes(_document([_page(1, spans)]), document) == []


def test_ror_revision_date_must_match_the_highlights_revision_date() -> None:
    assert _codes(_document([_ror_page(_REVISION_DATE, "AUG 26")])) == []

    findings = _findings(_document([_ror_page("JUN 27/26", "JUL 26")]))

    assert [finding.control for finding in findings] == [revision.ROR_REVISION_DATE]
    assert findings[0].original == "JUN 27/26"
    assert findings[0].proposed == _REVISION_DATE
