import fitz

from app.checks.thales_rules.page_classifier import identify_tp1_pages
from app.core.preparation_check_service import _apply_ocr_text
from app.core.preparation_readability import native_text_is_usable
from app.parsers.pdf_parser import parse_pdf


def test_native_text_requires_enough_legible_content() -> None:
    readable_text = "Readable technical text with numbered values and instructions. " * 3

    assert native_text_is_usable(readable_text) is True
    assert native_text_is_usable("Short title") is False
    assert native_text_is_usable("\ufffd" * 120) is False


def test_ocr_text_and_boxes_are_used_to_classify_scanned_pages() -> None:
    pdf = fitz.open()
    pdf.new_page(width=400, height=600)
    pdf_bytes = pdf.tobytes()
    pdf.close()
    parsed = parse_pdf(pdf_bytes)

    _apply_ocr_text(
        parsed,
        [{"page": 1, "needs_ocr": True}],
        {
            "1": {
                "text": "TP1\n12-34-56",
                "boxes": [
                    {"x0": 0.1, "y0": 0.93, "x1": 0.2, "y1": 0.95, "text": "TP1"},
                    {
                        "x0": 0.3,
                        "y0": 0.93,
                        "x1": 0.5,
                        "y1": 0.95,
                        "text": "12-34-56",
                    },
                ],
            }
        },
    )

    identify_tp1_pages(parsed, revision_date=None, cmm_number="12-34-56")

    assert parsed.pages[0].has_text_layer is False
    assert parsed.pages[0].page_type == "TP1"
