from __future__ import annotations

from types import SimpleNamespace

import fitz
import pytest

from app.checks.thales_rules import rules as thales_rules
from app.checks.thales_rules.operations import OPERATIONS
from app.core.compiled_rule_executor import execute_pdf_rules
from app.parsers.pdf_parser import parse_pdf

RULES = {definition.code: definition for definition in thales_rules.RULE_DEFINITIONS}
Placed = tuple[float, float, str]


def _parse(pages: list[list[Placed]]):
    pdf = fitz.open()
    for items in pages:
        page = pdf.new_page(width=600, height=800)
        for x, y, text in items:
            page.insert_text((x, y), text, fontsize=10)
    parsed = parse_pdf(pdf.tobytes())
    pdf.close()
    return parsed


def _document(**metadata: str) -> SimpleNamespace:
    return SimpleNamespace(client_metadata=metadata, **metadata)


def _status(code: str, parsed, document, *, page: int | None = None) -> str:
    rule = RULES[code].compiled_rule
    scoped = parsed
    if page is not None:
        from app.core.page_range import filter_pdf_pages

        scoped = filter_pdf_pages(parsed, [page])
    results, _ = execute_pdf_rules(
        scoped, [rule], db=None, document=document, client_operations=OPERATIONS
    )
    return results[0].status


def _lines(*texts: str, top: float = 80) -> list[Placed]:
    return [(40, top + index * 18, text) for index, text in enumerate(texts)]


def test_all_new_rules_are_preparation_rules() -> None:
    codes = [code for code in RULES if code.startswith("CUSTOM_PREP_")]

    assert len(codes) == 11
    assert all(RULES[code].preparation for code in codes)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Refer to Standard Practices Manual ATA No. 39-50-00 for details.", "FAIL"),
        ("Refer to Standard Practice ATA No. 20-03-00.", "FAIL"),
        ("Refer to Standard Practices Manual ATA No. 20-02-00 for details.", "PASS"),
        ("No reference to practices here. ATA No. 39-50-00 is another manual.", "PASS"),
    ],
)
def test_standard_practices_must_cite_ata_20_02_00(text: str, expected: str) -> None:
    parsed = _parse([_lines(text)])

    assert _status("CUSTOM_PREP_STANDARD_PRACTICE_ATA", parsed, _document()) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Use the Standard Electronic Hardware Practice 39-50-00.", "FAIL"),
        ("Use the standard electronic hardware Practice 39-50-00", "FAIL"),
        ("Use the Standard Practice Manual ATA No. 20-02-00.", "PASS"),
    ],
)
def test_legacy_electronic_hardware_practice_is_replaced(text: str, expected: str) -> None:
    parsed = _parse([_lines(text)])

    assert _status("CUSTOM_PREP_STANDARD_PRACTICE_REPLACE", parsed, _document()) == expected


def test_replacement_text_is_the_requested_manual_reference() -> None:
    rule = RULES["CUSTOM_PREP_STANDARD_PRACTICE_REPLACE"].compiled_rule

    assert rule.checks[0].replacement == "Standard Practice Manual ATA No. 20-02-00"


def _highlights(parsed) -> None:
    for page in parsed.pages:
        page.page_type = "HIGHLIGHTS"


def test_highlights_date_and_number_must_match_the_new_revision() -> None:
    body = _lines("REVISION No. 03 DATED JUL 27/26", "Chapter/Section Designation")
    parsed = _parse([body])
    _highlights(parsed)
    new = _document(meta_revision_date="AUG 03/26", meta_revision_number="04")
    current = _document(meta_revision_date="JUL 27/26", meta_revision_number="03")

    assert _status("CUSTOM_PREP_HIGHLIGHTS_REVISION_DATE", parsed, new) == "FAIL"
    assert _status("CUSTOM_PREP_HIGHLIGHTS_REVISION_NUMBER", parsed, new) == "FAIL"
    assert _status("CUSTOM_PREP_HIGHLIGHTS_REVISION_DATE", parsed, current) == "PASS"
    assert _status("CUSTOM_PREP_HIGHLIGHTS_REVISION_NUMBER", parsed, current) == "PASS"


def test_highlights_footer_date_must_match_the_new_revision() -> None:
    footer = [(40, 770, "Highlights Page 2"), (400, 770, "JUL 27/26")]
    parsed = _parse([_lines("REVISION No. 03 DATED JUL 27/26") + footer])
    _highlights(parsed)

    stale = _document(meta_revision_date="AUG 03/26")
    updated = _document(meta_revision_date="JUL 27/26")

    assert _status("CUSTOM_PREP_HIGHLIGHTS_FOOTER_DATE", parsed, stale) == "FAIL"
    assert _status("CUSTOM_PREP_HIGHLIGHTS_FOOTER_DATE", parsed, updated) == "PASS"


def _ror_page(*rows: str) -> list[Placed]:
    header: list[Placed] = [
        (40, 60, "RECORD OF REVISIONS"),
        (40, 100, "REV. No."),
        (140, 100, "REVISION DATE"),
        (280, 100, "INSERTION DATE"),
        (420, 100, "BY"),
    ]
    placed: list[Placed] = []
    for index, row in enumerate(rows):
        number, revision_date, insertion_date, author = row.split("|")
        top = 130 + index * 18
        placed += [
            (40, top, number),
            (140, top, revision_date),
            (280, top, insertion_date),
            (420, top, author),
        ]
    return header + placed


@pytest.mark.parametrize(
    ("revision_date", "insertion", "expected_when_present"),
    [
        ("JUL 14/26", "JUL 26", "PASS"),
        ("JUL 15/26", "AUG 26", "PASS"),
        ("DEC 20/26", "JAN 27", "PASS"),
        ("JUL 15/26", "JUL 26", "FAIL"),
    ],
)
def test_ror_new_row_uses_the_insertion_month_rule(
    revision_date: str, insertion: str, expected_when_present: str
) -> None:
    parsed = _parse([_ror_page("01|JUL 10/25|JUL 25|AB", f"02|{revision_date}|{insertion}|AB")])
    parsed.pages[0].page_type = "ROR"
    document = _document(meta_revision_date=revision_date, meta_revision_number="02")

    assert _status("CUSTOM_PREP_ROR_NEW_ROW", parsed, document) == expected_when_present


def test_ror_new_row_is_missing_until_it_is_added() -> None:
    parsed = _parse([_ror_page("01|JUL 10/25|JUL 25|AB")])
    parsed.pages[0].page_type = "ROR"
    document = _document(meta_revision_date="JUL 14/26", meta_revision_number="02")
    rule = RULES["CUSTOM_PREP_ROR_NEW_ROW"].compiled_rule

    results, _ = execute_pdf_rules(
        parsed, [rule], db=None, document=document, client_operations=OPERATIONS
    )

    assert results[0].status == "FAIL"


def test_ror_new_row_needs_a_day_in_the_mapped_revision_date() -> None:
    parsed = _parse([_ror_page("01|JUL 10/25|JUL 25|AB")])
    parsed.pages[0].page_type = "ROR"

    status = _status(
        "CUSTOM_PREP_ROR_NEW_ROW", parsed, _document(meta_revision_date="JUL 2026")
    )

    assert status == "INCONCLUSIVE"


def _lep_page(*rows: str) -> list[Placed]:
    placed: list[Placed] = [
        (40, 60, "LIST OF EFFECTIVE PAGES"),
        (40, 100, "SUBJECT"),
        (200, 100, "PAGE"),
        (320, 100, "DATE"),
    ]
    for index, row in enumerate(rows):
        subject, page_key, date_text = row.split("|")
        top = 130 + index * 18
        placed += [(40, top, subject), (200, top, page_key), (320, top, date_text)]
    return placed


def _lep_document(entry_date: str):
    footer = [(40, 770, "TP 1"), (400, 770, "JUL 27/26")]
    parsed = _parse(
        [
            _lep_page(f"Title page|TP 1|{entry_date}", "Highlights|Highlights 1|JUL 27/26")
            + [(40, 770, "LEP 1")],
            _lines("Title page body") + footer,
        ]
    )
    parsed.pages[0].page_type = "LEP"
    return parsed


@pytest.mark.parametrize(
    ("entry_date", "commented", "expected"),
    [
        ("JUL 27/26", True, "FAIL"),
        ("AUG 03/26", True, "FAIL"),
        ("AUG 03/26 *", True, "PASS"),
        ("JUL 27/26", False, "PASS"),
    ],
)
def test_lep_lists_commented_pages_with_the_new_date_and_a_star(
    entry_date: str, commented: bool, expected: str
) -> None:
    parsed = _lep_document(entry_date)
    parsed.pages[1].is_modified = True if commented else None
    document = _document(meta_revision_date="AUG 03/26")

    assert _status("CUSTOM_PREP_LEP_MODIFIED_PAGES", parsed, document, page=1) == expected


def test_detection_flags_the_lep_once_other_pages_are_decided_modified() -> None:
    from app.checks.thales_rules.preparation_detector import detect_pages_to_modify

    parsed = _parse(
        [
            _lep_page("Title page|TP 1|JUL 27/26") + [(40, 770, "LEP 1"), (400, 770, "JUL 27/26")],
            _lines("Use the Standard Electronic Hardware Practice 39-50-00.")
            + [(40, 770, "TP 1"), (400, 770, "JUL 27/26")],
            _lines("Unrelated page text") + [(40, 770, "Page 650")],
        ]
    )
    document = _document(meta_revision_date="AUG 03/26")
    bundle = SimpleNamespace(
        page_classifier=None, operations=OPERATIONS, mapping=SimpleNamespace(entities={})
    )
    rules = [
        RULES[code].compiled_rule
        for code in (
            "CUSTOM_PREP_LEP_MODIFIED_PAGES",
            "CUSTOM_PREP_STANDARD_PRACTICE_REPLACE",
        )
    ]

    decisions = detect_pages_to_modify(parsed, document, rules, None, bundle, {}, {})

    by_page = {item["page"]: item for item in decisions}
    assert [item["page"] for item in decisions] == [1, 2, 3]
    assert by_page[1]["page_type"] == "LEP"
    assert by_page[2]["is_modified"] is True
    assert by_page[3]["is_modified"] is False
    assert by_page[1]["is_modified"] is True
    assert [item["rule_id"] for item in by_page[1]["failures"]] == [
        "CUSTOM_PREP_LEP_MODIFIED_PAGES"
    ]


def test_lep_without_any_commented_page_or_date_passes_or_stays_open() -> None:
    parsed = _lep_document("JUL 27/26")
    parsed.pages[1].is_modified = True

    status = _status("CUSTOM_PREP_LEP_MODIFIED_PAGES", parsed, _document(), page=1)

    assert status == "INCONCLUSIVE"


def _toc(parsed_pages: list[list[Placed]], types: list[str]):
    parsed = _parse(parsed_pages)
    for page, page_type in zip(parsed.pages, types, strict=True):
        page.page_type = page_type
    return parsed


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        (["TABLE OF CONTENTS", "INTRODUCTION 1", "TESTING 101"], "PASS"),
        (["TABLE OF CONTENTS", "1. INTRODUCTION", "TESTING 101"], "PASS"),
        (["TABLE OF CONTENTS", "TESTING 101", "REPAIR 601"], "FAIL"),
    ],
)
def test_table_of_contents_must_list_the_introduction(entries: list[str], expected: str) -> None:
    parsed = _toc([_lines(*entries)], ["TABLE_OF_CONTENTS"])

    assert _status("CUSTOM_PREP_TOC_INTRODUCTION", parsed, _document()) == expected


def test_toc_introduction_is_reported_once_on_the_first_toc_page() -> None:
    parsed = _toc(
        [_lines("TABLE OF CONTENTS", "TESTING 101"), _lines("REPAIR 601")],
        ["TABLE_OF_CONTENTS", "TABLE_OF_CONTENTS"],
    )
    document = _document()

    assert _status("CUSTOM_PREP_TOC_INTRODUCTION", parsed, document, page=1) == "FAIL"
    assert _status("CUSTOM_PREP_TOC_INTRODUCTION", parsed, document, page=2) == "PASS"


_AIRBUS_SHOP = (
    "Shop Verification:",
    "A. Verification of the procedures in this manual",
    "(1) The shop verification will be done at the first repair of the equipment.",
)
_BOEING_SHOP = (
    "Shop Verification:",
    "A. Verification of the procedures in this manual",
    "(1) Testing and Fault Isolation: shop verification done JUN 24/88.",
)


@pytest.mark.parametrize(
    ("manufacturer", "shop", "expected"),
    [
        ("Airbus", _AIRBUS_SHOP, "PASS"),
        ("Airbus", _BOEING_SHOP, "FAIL"),
        ("Boeing", _BOEING_SHOP, "PASS"),
        ("Boeing", _AIRBUS_SHOP, "FAIL"),
    ],
)
def test_introduction_shop_verification_follows_the_mapped_manufacturer(
    manufacturer: str, shop: tuple[str, ...], expected: str
) -> None:
    parsed = _toc([_lines("INTRODUCTION", *shop)], ["INTRODUCTION"])

    status = _status(
        "CUSTOM_PREP_INTRODUCTION_SHOP_VERIFICATION",
        parsed,
        _document(meta_manufacturer=manufacturer),
    )

    assert status == expected


_TESTING_INTRO = (
    "NOTE: During testing operations, make sure that the environmental"
    " conditions are as follows:"
)
_HUMIDITY = (
    "- Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00,",
    "F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure.",
)


def test_testing_humidity_note_must_be_up_to_date() -> None:
    current = _toc(
        [_lines(_TESTING_INTRO, "- Temperature: 15 to 35 deg. C", *_HUMIDITY)], ["TESTING"]
    )
    outdated = _toc(
        [
            _lines(
                _TESTING_INTRO,
                "- Temperature: 15 to 35 deg. C",
                "- Relative humidity: 20 to 80 percent.",
            )
        ],
        ["TESTING"],
    )

    assert _status("CUSTOM_PREP_TESTING_HUMIDITY_NOTE", current, _document()) == "PASS"
    assert _status("CUSTOM_PREP_TESTING_HUMIDITY_NOTE", outdated, _document()) == "FAIL"


def test_testing_stabilization_note_must_be_present() -> None:
    note = "NOTE: Before the tests, let the equipment stay in these conditions for two hours minimum."
    present = _toc([_lines("Body", note)], ["TESTING"])
    missing = _toc([_lines("Body", "NOTE: Before the tests, wait one hour.")], ["TESTING"])

    assert _status("CUSTOM_PREP_TESTING_STABILIZATION_NOTE", present, _document()) == "PASS"
    assert _status("CUSTOM_PREP_TESTING_STABILIZATION_NOTE", missing, _document()) == "FAIL"
