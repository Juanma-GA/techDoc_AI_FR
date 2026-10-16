from __future__ import annotations

from PIL import Image

from app.services import image_replacement
from app.services.image_replacement import apply_replacements


def test_duplicate_reference_pairs_replace_separate_occurrences_in_order(monkeypatch) -> None:
    drawn_replacements: list[tuple[str, float]] = []

    def record_replacement(draw, polygon, text: str, fill, *, font_size: int) -> None:
        drawn_replacements.append((text, polygon[0][0]))

    monkeypatch.setattr(image_replacement, "_draw_replacement_text", record_replacement)

    _, applied_counts, _ = apply_replacements(
        Image.new("RGB", (180, 60), (215, 220, 225)),
        [
            {
                "text": "R-001 R-001 R-001",
                "box": [[10, 10], [170, 10], [170, 30], [10, 30]],
            }
        ],
        [
            {"reference": "R-001", "replacement": "101"},
            {"reference": "R-001", "replacement": "202"},
        ],
        replacement_font_size=14,
    )

    assert applied_counts == [1, 1]
    assert [text for text, _ in drawn_replacements] == ["101", "202"]
    assert drawn_replacements[0][1] < drawn_replacements[1][1]


def test_single_reference_pair_replaces_only_first_occurrence(monkeypatch) -> None:
    drawn_replacements: list[tuple[str, float]] = []
    monkeypatch.setattr(
        image_replacement,
        "_draw_replacement_text",
        lambda draw, polygon, text, fill, **kwargs: drawn_replacements.append(
            (text, polygon[0][0])
        ),
    )

    _, applied_counts, _ = apply_replacements(
        Image.new("RGB", (120, 60), "white"),
        [{"text": "R-001 R-001", "box": [[10, 10], [110, 10], [110, 30], [10, 30]]}],
        [{"reference": "R-001", "replacement": "101"}],
        replacement_font_size=14,
    )

    assert applied_counts == [1]
    assert [text for text, _ in drawn_replacements] == ["101"]
    assert drawn_replacements[0][1] < 60


def test_replacement_uses_local_background_instead_of_white_rectangle() -> None:
    background = (215, 220, 225)
    source = Image.new("RGB", (80, 40), background)

    result, applied_counts, _ = apply_replacements(
        source,
        [{"text": "R1", "box": [[10, 10], [50, 10], [50, 30], [10, 30]]}],
        [{"reference": "R1", "replacement": "7"}],
        replacement_font_size=14,
    )

    assert applied_counts == [1]
    assert result.getpixel((11, 11)) == background
    assert any(
        pixel[0] < 80 and pixel[1] < 80 and pixel[2] < 80
        for pixel in result.crop((10, 10, 50, 30)).getdata()
    )
