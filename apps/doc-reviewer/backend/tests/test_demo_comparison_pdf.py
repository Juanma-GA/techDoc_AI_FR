"""Verify the authorized anonymous demo fixtures with the real comparison engine."""

from pathlib import Path

import pymupdf

from app.core.comparison_report import build_comparison_report


DEMO_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo"
FILENAMES = ["DEMO_CMM_PDF_anonyme.pdf", "DEMO_CMM_PDF_revision_anonyme.pdf"]
EXPECTED_CHANGES = {
    (1, "REVISION No. 01 DATED JUL 27/26", "REVISION No. 02 DATED JUL 27/26"),
    (1, "New presentation and new date.", "New presentation and new data."),
    (1, "Page 701 to 704", "Page 701 to 702"),
    (2, "1-900-SB", "1-901-SB"),
}


def test_demo_revision_has_exactly_four_localized_comparison_changes() -> None:
    report = build_comparison_report(
        [DEMO_DIR / filename for filename in FILENAMES], FILENAMES, 0,
    )
    assert [document["page_count"] for document in report["documents"]] == [2, 2]
    comparison = report["comparisons"][0]
    assert comparison["added_count"] == 4
    assert comparison["removed_count"] == 4
    assert [
        (pair["reference_page"], pair["comparison_page"], pair["status"])
        for pair in comparison["page_alignment"]
    ] == [(1, 1, "changed"), (2, 2, "changed")]
    assert {
        (change["page"], change["text"])
        for change in comparison["changes"] if change["kind"] == "removed"
    } == {(page, before) for page, before, _after in EXPECTED_CHANGES}
    assert {
        (change["page"], change["text"])
        for change in comparison["changes"] if change["kind"] == "added"
    } == {(page, after) for page, _before, after in EXPECTED_CHANGES}
    for change in comparison["changes"]:
        box = change["bbox"]
        assert 0 <= box["x0"] < box["x1"] <= box["page_w"]
        assert 0 <= box["y0"] < box["y1"] <= box["page_h"]


def test_demo_revision_preserves_geometry_fonts_and_text_order() -> None:
    with (
        pymupdf.open(DEMO_DIR / FILENAMES[0]) as original,
        pymupdf.open(DEMO_DIR / FILENAMES[1]) as revision,
    ):
        for page_number, (before, after) in enumerate(zip(original, revision, strict=True), 1):
            assert before.rect == after.rect
            assert before.rotation == after.rotation
            assert [font[3:] for font in before.get_fonts()] == [
                font[3:] for font in after.get_fonts()
            ]
            expected_text = before.get_text()
            for page, old_text, new_text in EXPECTED_CHANGES:
                if page == page_number:
                    expected_text = expected_text.replace(old_text, new_text)
            assert after.get_text() == expected_text
            before_words = before.get_text("words")
            after_words = after.get_text("words")
            assert len(before_words) == len(after_words)
            for before_word, after_word in zip(before_words, after_words, strict=True):
                assert before_word[:4] == after_word[:4]
