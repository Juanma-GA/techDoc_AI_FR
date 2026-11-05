from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.checks.thales_rules.ata100 import operations
from app.checks.thales_rules.ata100.additional_rules import (
    CUSTOM_LEP_PAGE_COLUMN_ALIGNMENT,
    CUSTOM_LIST_OF_MATERIALS_CODE_SUPPLIER_DEFAULTS,
    CUSTOM_LIST_OF_MATERIALS_ROW_ALIGNMENT,
    CUSTOM_MATERIALS_TABLE_NO_NOTE,
)
from app.checks.thales_rules.ata100.lep_alignment_operations import (
    LEP_PAGE_COLUMN_ALIGNMENT,
)
from app.checks.thales_rules.ata100.materials_operations import MATERIALS_CHECKS
from app.checks.thales_rules.ata100.revision_bar_scope import (
    is_revision_bar_exempt_page,
)
from app.checks.thales_rules.ata100.revision_engine import (
    HighlightsEntry,
    RevisionState,
)
from app.checks.thales_rules.ata100.rules import CUSTOM_REPAIR_NOTE
from app.core.compiled_rule_executor import execute_pdf_rules
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, PdfVectorPrimitive, Span


def _span(
    text: str,
    x: float,
    y: float,
    *,
    width: float = 80.0,
    height: float = 8.0,
) -> Span:
    return Span(text, (x, y, x + width, y + height), 1, "Arial", 10.0)


def _context(page: ParsedPage) -> SimpleNamespace:
    parsed_pdf = ParsedPdf(
        page_count=page.page,
        pages=[page],
        full_text=page.text,
        is_signed=False,
    )
    return SimpleNamespace(
        runtime=SimpleNamespace(parsed_pdf=parsed_pdf, document=None, is_docx=False),
        targets=(),
    )


def _materials_page(
    title: str = "LIST OF MATERIALS",
    *,
    code: str | None = "not specific",
    supplier: str = "Commercially available",
    code_y: float = 130.0,
    note: tuple[str, float] | None = None,
    note_before_table: bool = False,
) -> ParsedPage:
    spans = [
        _span(title, 180.0, 20.0, width=200.0),
        _span("DESIGNATION", 35.0, 100.0),
        _span("CODE", 180.0, 100.0, width=30.0),
        _span("SUPPLIERS TRADE NAME AND CODE FSCM", 265.0, 100.0, width=150.0),
        _span("USE", 450.0, 100.0, width=30.0),
        _span("Seal", 35.0, 130.0),
        _span("X", 455.0, 130.0, width=8.0),
    ]
    if code is not None:
        spans.append(_span(code, 180.0, code_y, width=80.0))
    if supplier:
        spans.append(_span(supplier, 265.0, 130.0, width=150.0))
    if note is not None:
        text, y = note
        spans.append(_span(text, 270.0, y, width=150.0))
    if note_before_table:
        spans.append(_span("NOTE: Equivalent substitutes may be used.", 35.0, 50.0, width=250.0))
    text = "\n".join(span.text for span in spans)
    return ParsedPage(page=1, text=text, spans=spans, page_width=612.0, page_height=792.0)


def _lep_page(second_page_x: float = 202.0) -> ParsedPage:
    spans = [
        _span("LIST OF EFFECTIVE PAGES", 200.0, 20.0, width=200.0),
        _span("SUBJECT", 40.0, 60.0),
        _span("PAGE", 200.0, 60.0),
        _span("DATE", 300.0, 60.0),
        _span("Inspection", 40.0, 90.0),
        _span("101", 202.0, 90.0, width=25.0),
        _span("JAN 23/24", 300.0, 90.0),
        _span("102", second_page_x, 110.0, width=25.0),
        _span("JAN 23/24", 300.0, 110.0),
    ]
    return ParsedPage(
        page=1,
        text="\n".join(span.text for span in spans),
        spans=spans,
        page_width=612.0,
        page_height=792.0,
    )


def _revision_context(
    title: str,
    *,
    status: str,
    page_type: str | None = None,
    page_key: str = "TEST 1",
    bars: list[PdfVectorPrimitive] | None = None,
) -> SimpleNamespace:
    page = ParsedPage(
        page=1,
        text=title,
        spans=[_span(title, 100.0, 150.0, width=300.0)],
        page_type=page_type,
        page_width=612.0,
        page_height=792.0,
        vector_primitives=bars or [],
    )
    parsed_pdf = ParsedPdf(
        page_count=1,
        pages=[page],
        full_text=title,
        is_signed=False,
    )
    state = RevisionState(
        highlights=[
            HighlightsEntry(
                subject="Test",
                pages_text=page_key,
                page_keys=(page_key,),
                status=status,
                page=1,
                bbox=(0.0, 0.0, 0.0, 0.0),
                status_bbox=(0.0, 0.0, 0.0, 0.0),
            )
        ],
        expected_footer_keys={1: page_key},
    )
    setattr(parsed_pdf, operations._REVISION_STATE_ATTR, state)
    return SimpleNamespace(
        runtime=SimpleNamespace(parsed_pdf=parsed_pdf, document=None, is_docx=False),
        targets=(),
    )


def _bar(x: float, top: float, bottom: float) -> PdfVectorPrimitive:
    return PdfVectorPrimitive(
        kind="line",
        bbox=(x, top, x, bottom),
        color=(0.0, 0.0, 0.0),
        fill=None,
        width=2.28,
    )


def test_revision_bar_exemptions_cover_the_requested_list_families() -> None:
    for title in (
        "VENDOR CODE LIST",
        "NUMERICAL INDEX",
        "EQUIPMENT DESIGNATOR INDEX",
        "PARTS LIST",
        "GEO LOC",
        "OPTIONAL PARTS LIST",
    ):
        page = ParsedPage(page=1, text=title, spans=[])
        assert is_revision_bar_exempt_page(page, None), title

    assert not is_revision_bar_exempt_page(
        ParsedPage(page=1, text="ILLUSTRATED PARTS LIST", spans=[]),
        None,
    )


def test_all_revision_bar_controls_skip_exempt_page_families() -> None:
    cases = (
        ("revision_bar_new", "N", None, "VCL 1", [_bar(90.0, 180.0, 300.0)]),
        ("revision_bar_modified", "R", None, "VCL 1", []),
        ("revision_bar_margin", "R", None, "VCL 1", [_bar(90.0, 180.0, 300.0)]),
        ("revision_bar_tp1_footer", "R", "TP1", "TP 1", []),
        ("revision_bar_tp2_body", "R", "TP2", "TP 2", []),
    )
    for control, status, page_type, page_key, bars in cases:
        result = operations.DOCUMENT_STRUCTURE.execute(
            _revision_context(
                "OPTIONAL PARTS LIST",
                status=status,
                page_type=page_type,
                page_key=page_key,
                bars=bars,
            ),
            {"control": control},
        )
        expected_status = "PASS" if control == "revision_bar_tp2_body" else "INCONCLUSIVE"
        assert result.status == expected_status, control


def test_revision_bar_exemption_uses_exact_page_key_prefixes() -> None:
    page = ParsedPage(page=1, text="", spans=[])
    for page_key in ("VCL 1", "NI 1", "EDI 1", "PL 1", "GEO LOC 1", "OPL 1"):
        assert is_revision_bar_exempt_page(page, page_key), page_key
    assert not is_revision_bar_exempt_page(page, "TP 1")


def test_relative_humidity_accepts_supported_dash_variants() -> None:
    base = (
        "NOTE: During repair operations, make sure that the environmental "
        "conditions are as follows:\n"
        "Pressure: 1 bar\n"
        "Relative humidity: Refer to Standard Practices Manual ATA No. "
        "20-02-00, F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
    )
    for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212", "\ufffd"):
        text = base.replace("-", dash)
        parsed_pdf = ParsedPdf(
            page_count=1,
            pages=[ParsedPage(page=1, text=f"REPAIR\n{text}", spans=[], page_type="REPAIR")],
            full_text=f"REPAIR\n{text}",
            is_signed=False,
        )
        results, _suggestions = execute_pdf_rules(
            parsed_pdf,
            [CUSTOM_REPAIR_NOTE.compiled_rule],
        )
        assert results[0].status == "PASS", repr(dash)


def test_lep_page_column_alignment_detects_a_shifted_page_number() -> None:
    aligned = LEP_PAGE_COLUMN_ALIGNMENT.execute(_context(_lep_page()), {})
    shifted_context = _context(_lep_page(second_page_x=225.0))
    shifted = LEP_PAGE_COLUMN_ALIGNMENT.execute(shifted_context, {})

    assert aligned.status == "PASS"
    assert shifted.status == "FAIL"
    assert LEP_PAGE_COLUMN_ALIGNMENT.suggestions is not None
    assert LEP_PAGE_COLUMN_ALIGNMENT.suggestions(shifted_context, {})[0].observed == "102"
    assert CUSTOM_LEP_PAGE_COLUMN_ALIGNMENT.code == "CUSTOM_LEP_PAGE_COLUMN_ALIGNMENT"


@pytest.mark.parametrize(
    "title",
    ("LIST OF MATERIALS", "LIST OF CONSUMABLES", "SPECIAL EQUIPMENT AND TOOLING"),
)
def test_note_inside_a_consumables_or_equipment_table_fails(title: str) -> None:
    context = _context(
        _materials_page(
            title,
            note=("NOTE: Equivalent substitutes may be used.", 135.0),
        )
    )

    result = MATERIALS_CHECKS.execute(
        context,
        {"control": "no_notes_in_tables"},
    )
    assert result.status == "FAIL"


def test_note_before_materials_table_is_allowed() -> None:
    result = MATERIALS_CHECKS.execute(
        _context(_materials_page(note_before_table=True)),
        {"control": "no_notes_in_tables"},
    )
    assert result.status == "PASS"
    assert CUSTOM_MATERIALS_TABLE_NO_NOTE.code == "CUSTOM_MATERIALS_TABLE_NO_NOTE"


def test_list_of_materials_cells_must_be_top_aligned() -> None:
    aligned = MATERIALS_CHECKS.execute(
        _context(_materials_page()),
        {"control": "row_alignment"},
    )
    shifted_code = MATERIALS_CHECKS.execute(
        _context(_materials_page(code_y=140.0)),
        {"control": "row_alignment"},
    )

    assert aligned.status == "PASS"
    assert shifted_code.status == "FAIL"
    assert CUSTOM_LIST_OF_MATERIALS_ROW_ALIGNMENT.code == ("CUSTOM_LIST_OF_MATERIALS_ROW_ALIGNMENT")


def test_missing_materials_code_requires_both_default_values() -> None:
    context = _context(_materials_page(code=None, supplier=""))
    result = MATERIALS_CHECKS.execute(
        context,
        {"control": "code_supplier_defaults"},
    )
    suggestions = MATERIALS_CHECKS.suggestions

    assert result.status == "FAIL"
    assert result.expected == "not specific"
    assert suggestions is not None
    findings = suggestions(context, {"control": "code_supplier_defaults"})
    assert [finding.expected for finding in findings] == [
        "not specific",
        "Commercially available",
    ]
    assert CUSTOM_LIST_OF_MATERIALS_CODE_SUPPLIER_DEFAULTS.code == (
        "CUSTOM_LIST_OF_MATERIALS_CODE_SUPPLIER_DEFAULTS"
    )


def test_materials_default_values_pass_when_code_is_not_specific() -> None:
    result = MATERIALS_CHECKS.execute(
        _context(_materials_page(code="not specific", supplier="Commercially available")),
        {"control": "code_supplier_defaults"},
    )
    assert result.status == "PASS"
