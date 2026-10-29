from __future__ import annotations

from types import SimpleNamespace
import fitz

from app.checks.client_registry import load_active_client_configuration
from app.checks.thales_rules.operations import _paragraphs_from_pdf_page
from app.checks.thales_rules.page_classifier import classify_pages
from app.core.compiled_rule_executor import execute_pdf_rules
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, PdfLine, Span, parse_pdf


_RULE_CODE = "CUSTOM_PARAGRAPH_JUSTIFICATION"
_CONFIGURATION = load_active_client_configuration()
_RULE = next(
    definition.compiled_rule
    for definition in _CONFIGURATION.bundle.rules
    if definition.code == _RULE_CODE
)
_SAMPLE_PARAGRAPH = (
    "Each component must be inspected before the next maintenance operation. "
    "Verify that the specified equipment is correctly positioned and secure. "
    "All applicable procedures shall be completed in the stated sequence. "
    "Record the inspection results and report any discrepancy to the responsible authority. "
    "The maintenance record must identify the equipment, the procedure, and the date of completion."
)


def _pdf_page(right_edges: list[float], *, modified: bool = True) -> ParsedPdf:
    paragraph_lines = [
        "Each component must be inspected before the next maintenance operation.",
        "Verify that the specified equipment is correctly positioned and secure.",
        "All applicable procedures shall be completed in the stated sequence.",
        "Record the final inspection results.",
    ]
    lines = [
        PdfLine(
            text=text,
            bbox=(60.0 if index == 0 else 50.0, 150.0 + index * 16.0, right_edges[index], 161.0 + index * 16.0),
            block_index=1,
            line_index=index,
        )
        for index, text in enumerate(paragraph_lines)
    ]
    spans = [
        Span(text=line.text, bbox=line.bbox, page=1, font="Arial", size=10.0)
        for line in lines
    ]
    text = "\n".join(paragraph_lines)
    return ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text=text,
                spans=spans,
                is_modified=modified,
                lines=lines,
                page_height=800.0,
            )
        ],
        full_text=text,
        is_signed=False,
    )


def _three_line_pdf(right_edges: list[float]) -> ParsedPdf:
    paragraph_lines = [
        "Faulty parts should be replaced by approved spares only. After any ",
        "component has been renewed or repaired, carry out the full procedure in ",
        "TESTING. ",
    ]
    line_boxes = [
        (107.8, 144.7, right_edges[0], 158.8),
        (107.8, 158.8, right_edges[1], 173.0),
        (107.8, 173.0, right_edges[2], 187.1),
    ]
    lines = [
        PdfLine(text, box, block_index=1, line_index=index)
        for index, (text, box) in enumerate(zip(paragraph_lines, line_boxes))
    ]
    text = "\n".join(paragraph_lines)
    return ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text=text,
                spans=[
                    Span(text=line.text, bbox=line.bbox, page=1, font="Arial", size=10.0)
                    for line in lines
                ],
                is_modified=True,
                lines=lines,
                page_height=792.0,
            )
        ],
        full_text=text,
        is_signed=False,
    )


def _layout_pdf(
    lines: list[tuple[str, float, float]],
    *,
    line_indexes: list[int] | None = None,
) -> ParsedPdf:
    pdf_lines = [
        PdfLine(
            text,
            (left, 150.0 + index * 16.0, right, 161.0 + index * 16.0),
            block_index=1,
            line_index=index if line_indexes is None else line_indexes[index],
        )
        for index, (text, left, right) in enumerate(lines)
    ]
    text = "\n".join(line.text for line in pdf_lines)
    return ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text=text,
                is_modified=True,
                lines=pdf_lines,
                page_height=800.0,
            )
        ],
        full_text=text,
        is_signed=False,
    )


def _run_rule(parsed: ParsedPdf):
    return execute_pdf_rules(
        parsed,
        [_RULE],
        client_operations=_CONFIGURATION.bundle.operations,
        client_entities=_CONFIGURATION.bundle.mapping.entities,
    )


def _render_pdf(tmp_path, *, alignment: int) -> ParsedPdf:
    doc = fitz.open()
    page = doc.new_page(width=420, height=320)
    page.insert_textbox(
        fitz.Rect(50, 60, 340, 270),
        _SAMPLE_PARAGRAPH,
        fontname="helv",
        fontsize=11,
        align=alignment,
    )
    path = tmp_path / f"paragraph-{alignment}.pdf"
    doc.save(str(path))
    doc.close()

    parsed = parse_pdf(path)
    parsed.pages[0].is_modified = True
    return parsed


def test_justified_paragraph_passes_and_final_line_may_be_short() -> None:
    results, suggestions = _run_rule(_pdf_page([500.0, 500.0, 500.0, 190.0]))

    assert results[0].status == "PASS"
    assert suggestions == []


def test_short_sentence_final_line_is_ignored_when_other_edges_align() -> None:
    parsed = _layout_pdf(
        [
            ("The first justified line reaches the right margin as expected.", 50.0, 500.0),
            ("The second justified line reaches the same right margin too.", 50.0, 500.0),
            ("source. A pressure increase of 15 mb for 10 minutes is tolerated.", 50.0, 465.0),
            ("For example: in case of a leak the pointer shifts from zero.", 50.0, 430.0),
        ]
    )

    results, suggestions = _run_rule(parsed)

    assert results[0].status == "PASS"
    assert suggestions == []


def test_completed_list_note_does_not_skew_following_paragraph_alignment() -> None:
    parsed = _layout_pdf(
        [
            ("- Not applicable for this CMM ATA 22-44-44.", 20.0, 300.0),
            ("Refer to CMMs 22-43-18, 22-43-25B2, B3, B4 and B5 which contain", 50.0, 500.0),
            ("the section Testing and Fault Isolation or Automatic Test", 50.0, 390.0),
            ("Requirements for the board part number listed in the Title Page", 50.0, 500.0),
            ("of this CMM.", 50.0, 300.0),
        ]
    )

    results, suggestions = _run_rule(parsed)

    assert results[0].status == "PASS"
    assert suggestions == []


def test_missing_pdf_line_index_splits_paragraphs() -> None:
    parsed = _layout_pdf(
        [
            ("The first justified line has enough words for measurement.", 50.0, 500.0),
            ("The second justified line shares its right edge exactly.", 50.0, 500.0),
            ("short final line without terminal punctuation", 50.0, 400.0),
            ("A separate short note starts after an empty PDF line", 50.0, 450.0),
        ],
        line_indexes=[0, 1, 2, 4],
    )

    paragraphs = _paragraphs_from_pdf_page(parsed.pages[0])

    assert [len(paragraph) for paragraph in paragraphs] == [3, 1]


def test_left_aligned_paragraph_fails_without_text_replacement_suggestion() -> None:
    results, suggestions = _run_rule(_pdf_page([330.0, 410.0, 500.0, 190.0]))

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert suggestions[0].original == suggestions[0].proposed
    assert suggestions[0].bbox[0] == 60.0


def test_explicitly_unchanged_page_is_outside_rule_scope() -> None:
    results, suggestions = _run_rule(
        _pdf_page([330.0, 410.0, 500.0, 190.0], modified=False)
    )

    assert results == []
    assert suggestions == []


def test_three_line_unjustified_paragraph_is_detected_from_nonfinal_edges() -> None:
    results, suggestions = _run_rule(_three_line_pdf([509.8, 539.8, 161.8]))

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert "Faulty parts should be replaced" in suggestions[0].original
    assert suggestions[0].original == suggestions[0].proposed


def test_three_line_justified_paragraph_ignores_short_final_line() -> None:
    results, suggestions = _run_rule(_three_line_pdf([539.8, 539.8, 161.8]))

    assert results[0].status == "PASS"
    assert suggestions == []


def test_one_and_two_line_blocks_are_not_assessed() -> None:
    for line_count in (1, 2):
        parsed = _pdf_page([330.0, 410.0, 500.0, 190.0])
        page = parsed.pages[0]
        page.lines = page.lines[:line_count]
        page.spans = page.spans[:line_count]
        page.text = "\n".join(line.text for line in page.lines)
        parsed.full_text = page.text

        results, suggestions = _run_rule(parsed)

        assert results[0].status == "INCONCLUSIVE"
        assert suggestions == []


def test_table_of_contents_is_not_treated_as_body_paragraphs() -> None:
    parsed = _pdf_page([330.0, 410.0, 500.0, 190.0])
    page = parsed.pages[0]
    page.text = f"TABLE OF CONTENTS\n{page.text}"
    parsed.full_text = page.text

    results, suggestions = _run_rule(parsed)

    assert results[0].status == "INCONCLUSIVE"
    assert suggestions == []


def test_one_line_statement_and_list_items_are_not_combined_as_a_paragraph() -> None:
    parsed = _layout_pdf(
        [
            ("This ILLUSTRATED PARTS LIST (IPL) is prepared to ATA Specification 100.", 50.0, 500.0),
            ("It is divided as follows:", 50.0, 280.0),
            ("- INTRO: Introduction", 50.0, 240.0),
            ("- OPL: Optional Parts List", 50.0, 300.0),
            ("B. Function and Use", 50.0, 300.0),
        ]
    )

    results, suggestions = _run_rule(parsed)

    assert results[0].status == "INCONCLUSIVE"
    assert suggestions == []


def test_multicolumn_table_block_is_not_checked_as_a_paragraph() -> None:
    parsed = _layout_pdf(
        [
            ("AR:", 50.0, 70.0),
            ("As Required", 220.0, 320.0),
            ("AMDMNT:", 50.0, 110.0),
            ("Amendment", 220.0, 310.0),
            ("DET:", 50.0, 75.0),
            ("Detail", 220.0, 270.0),
            ("EFF:", 50.0, 75.0),
            ("Effectivity", 220.0, 310.0),
        ]
    )

    results, suggestions = _run_rule(parsed)

    assert results[0].status == "INCONCLUSIVE"
    assert suggestions == []


def test_table_headers_do_not_extend_a_two_line_prose_paragraph() -> None:
    parsed = _layout_pdf(
        [
            ("The Effectivity Code is a letter which shows the interchangeability", 50.0, 500.0),
            ("of the parts on a figure, as shown below:", 50.0, 350.0),
            ("FIGURE", 50.0, 120.0),
            ("ITEM", 250.0, 320.0),
        ]
    )

    results, suggestions = _run_rule(parsed)

    assert results[0].status == "INCONCLUSIVE"
    assert suggestions == []


def test_left_aligned_pdf_paragraph_is_detected_from_rendered_geometry(tmp_path) -> None:
    parsed = _render_pdf(tmp_path, alignment=fitz.TEXT_ALIGN_LEFT)

    assert len(parsed.pages[0].lines) >= 4
    results, suggestions = _run_rule(parsed)

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert suggestions[0].original == suggestions[0].proposed


def test_justified_pdf_paragraph_passes_from_rendered_geometry(tmp_path) -> None:
    parsed = _render_pdf(tmp_path, alignment=fitz.TEXT_ALIGN_JUSTIFY)

    assert len(parsed.pages[0].lines) >= 4
    results, suggestions = _run_rule(parsed)

    assert results[0].status == "PASS"
    assert suggestions == []


def test_faulty_paragraph_surfaces_as_detection_only() -> None:
    parsed = _three_line_pdf([509.8, 539.8, 161.8])
    document = SimpleNamespace(
        meta_revision_date="JUL 27/26",
        meta_first_issue_date=None,
        meta_last_issue_date=None,
        meta_cmm_number="79-30-01",
    )
    classify_pages(parsed, document)

    page = next(
        page for page in parsed.pages if "faulty parts should be replaced" in page.text.casefold()
    )
    results, suggestions = execute_pdf_rules(
        parsed,
        [_RULE],
        document=document,
        client_operations=_CONFIGURATION.bundle.operations,
        client_entities=_CONFIGURATION.bundle.mapping.entities,
    )
    finding = next(
        suggestion
        for suggestion in suggestions
        if suggestion.page == page.page
        and "Faulty parts should be replaced" in suggestion.original
    )

    assert page.is_modified is True
    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert suggestions[0].page == page.page
    assert finding.original == finding.proposed
    assert finding.bbox[2] > finding.bbox[0]


def test_rendered_faulty_paragraph_is_surfaced_as_detection_only(tmp_path) -> None:
    # Synthetic stand-in for the client manual page (never commit client documents).
    doc = fitz.open()
    pdf_page = doc.new_page(width=612, height=792)
    pdf_page.insert_textbox(
        fitz.Rect(107.8, 140, 540, 260),
        "Faulty parts should be replaced by approved spares only. After any component "
        "has been renewed or repaired, carry out the full procedure in TESTING AND "
        "FAULT ISOLATION before the unit is returned to service.",
        fontname="helv",
        fontsize=10,
        align=fitz.TEXT_ALIGN_LEFT,
    )
    path = tmp_path / "faulty-paragraph.pdf"
    doc.save(str(path))
    doc.close()

    parsed = parse_pdf(path)
    parsed.pages[0].is_modified = True
    page = parsed.pages[0]
    results, suggestions = _run_rule(parsed)
    finding = next(
        suggestion
        for suggestion in suggestions
        if "Faulty parts should be replaced" in suggestion.original
    )

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert suggestions[0].page == page.page
    assert finding.original == finding.proposed
    assert finding.bbox[2] > finding.bbox[0]