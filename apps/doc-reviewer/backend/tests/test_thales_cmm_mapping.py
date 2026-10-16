from types import SimpleNamespace

from app.checks.thales_rules.operations import OPERATIONS
from app.checks.thales_rules.rules import CUSTOM_CMM_MAPPING_SUSPECT, RULE_DEFINITIONS
from app.core.compiled_rule_executor import execute_pdf_rules
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, Span

_CMM_PATTERN = r"(?<!\w)(\d{2}-\d{2}-\d{2}[A-Za-z]?)(?!\w)"
_OPERATION = OPERATIONS["cmm_mapping_consistency"]


def _context(mapped_value: str, footer_values: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        runtime=SimpleNamespace(
            is_docx=False,
            parsed_pdf=object(),
            document=SimpleNamespace(meta_cmm_number=mapped_value),
            client_entities={"cmm_number": _CMM_PATTERN},
        ),
        targets=tuple(
            SimpleNamespace(raw_page=page, text=value)
            for page, value in enumerate(footer_values, start=1)
        ),
    )


def _parsed_pdf(footer_values: list[str]) -> ParsedPdf:
    pages = []
    for page_number, footer in enumerate(footer_values, start=1):
        body = f"Document body {page_number}"
        pages.append(
            ParsedPage(
                page=page_number,
                page_height=800,
                text=f"{body}\n{footer}",
                spans=[
                    Span(
                        text=body,
                        bbox=(40.0, 100.0, 200.0, 120.0),
                        page=page_number,
                        font="Arial",
                        size=10.0,
                    ),
                    Span(
                        text=footer,
                        bbox=(40.0, 760.0, 300.0, 780.0),
                        page=page_number,
                        font="Arial",
                        size=8.0,
                    ),
                ],
            )
        )
    return ParsedPdf(
        page_count=len(pages),
        pages=pages,
        full_text="\n".join(page.text for page in pages),
        is_signed=False,
    )


def test_cmm_mapping_consistency_warns_at_the_ninety_percent_threshold() -> None:
    result = _OPERATION.execute(
        _context("79-30-02", ["79-30-01"] * 9 + ["79-30-02"]),
        {},
    )

    assert result.status == "FAIL"
    assert result.severity == "warning"
    assert result.observed == "79-30-01"
    assert result.expected == "79-30-02"


def test_cmm_mapping_suspect_rule_runs_on_footer_targets() -> None:
    results, _ = execute_pdf_rules(
        _parsed_pdf(["79-30-01"] * 9 + ["79-30-02"]),
        [CUSTOM_CMM_MAPPING_SUSPECT.compiled_rule],
        document=SimpleNamespace(meta_cmm_number="79-30-02"),
        client_operations=OPERATIONS,
        client_entities={"cmm_number": _CMM_PATTERN},
    )

    assert results[0].status == "FAIL"
    assert results[0].evidence is not None
    assert results[0].evidence.observed_value == "79-30-01"
    assert results[0].evidence.expected_value == "79-30-02"


def test_cmm_mapping_consistency_does_not_warn_below_ninety_percent() -> None:
    result = _OPERATION.execute(
        _context("79-30-02", ["79-30-01"] * 8 + ["79-30-02"] * 2),
        {},
    )

    assert result.status == "PASS"


def test_cmm_mapping_consistency_does_not_warn_when_mapping_is_dominant() -> None:
    result = _OPERATION.execute(
        _context("79-30-02", ["79-30-02"] * 9 + ["79-30-01"]),
        {},
    )

    assert result.status == "PASS"


def test_cmm_mapping_consistency_accepts_added_a_suffix_for_a_base_mapping() -> None:
    result = _OPERATION.execute(
        _context("79-30-02", ["79-30-02A"] * 10),
        {},
    )

    assert result.status == "PASS"


def test_cmm_mapping_consistency_does_not_remove_a_mapped_a_suffix() -> None:
    result = _OPERATION.execute(
        _context("79-30-02A", ["79-30-02"] * 10),
        {},
    )

    assert result.status == "FAIL"


def test_cmm_mapping_consistency_ignores_ambiguous_pages() -> None:
    result = _OPERATION.execute(
        _context("79-30-02", ["79-30-01"] * 9 + ["79-30-02\n79-30-03"]),
        {},
    )

    assert result.status == "FAIL"


def test_cmm_mapping_consistency_is_inconclusive_without_detected_numbers() -> None:
    result = _OPERATION.execute(_context("79-30-02", ["Footer text"]), {})

    assert result.status == "INCONCLUSIVE"


def test_cmm_mapping_suspect_rule_is_registered_as_a_warning() -> None:
    check = CUSTOM_CMM_MAPPING_SUSPECT.compiled_rule.checks[0]

    assert CUSTOM_CMM_MAPPING_SUSPECT.compiled_rule.severity == "warning"
    assert check.operation == "cmm_mapping_consistency"
    assert CUSTOM_CMM_MAPPING_SUSPECT in RULE_DEFINITIONS
