from __future__ import annotations

from PIL import Image, ImageDraw

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
        broadcast_references={"R001"},
    )

    assert applied_counts == [1, 1]
    assert [text for text, _ in drawn_replacements] == ["101", "202"]
    assert drawn_replacements[0][1] < drawn_replacements[1][1]


def test_single_reference_pair_replaces_all_occurrences_with_the_same_value(monkeypatch) -> None:
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
        broadcast_references={"R001"},
    )

    assert applied_counts == [2]
    assert [text for text, _ in drawn_replacements] == ["101", "101"]
    assert drawn_replacements[0][1] < drawn_replacements[1][1]


def test_duplicate_identical_pairs_broadcast_all_occurrences(monkeypatch) -> None:
    drawn_replacements: list[str] = []
    monkeypatch.setattr(
        image_replacement,
        "_draw_replacement_text",
        lambda draw, polygon, text, fill, **kwargs: drawn_replacements.append(text),
    )

    _, applied_counts, _ = apply_replacements(
        Image.new("RGB", (180, 60), "white"),
        [{"text": "R-001 R-001 R-001", "box": [[10, 10], [170, 10], [170, 30], [10, 30]]}],
        [
            {"reference": "R-001", "replacement": "101"},
            {"reference": "R-001", "replacement": "101"},
        ],
        replacement_font_size=14,
        broadcast_references={"R001"},
    )

    assert applied_counts == [2, 1]
    assert drawn_replacements == ["101", "101", "101"]


def test_replacement_does_not_match_reference_inside_a_longer_token(monkeypatch) -> None:
    drawn_replacements: list[str] = []
    monkeypatch.setattr(
        image_replacement,
        "_draw_replacement_text",
        lambda draw, polygon, text, fill, **kwargs: drawn_replacements.append(text),
    )

    _, applied_counts, _ = apply_replacements(
        Image.new("RGB", (120, 60), "white"),
        [{"text": "XXXYY*", "box": [[10, 10], [110, 10], [110, 30], [10, 30]]}],
        [{"reference": "XXXY", "replacement": "101"}],
        replacement_font_size=14,
    )

    assert applied_counts == [0]
    assert drawn_replacements == []


def test_replacement_does_not_match_a_numeric_suffix_separated_by_ocr_spaces(monkeypatch) -> None:
    drawn_replacements: list[str] = []
    monkeypatch.setattr(
        image_replacement,
        "_draw_replacement_text",
        lambda draw, polygon, text, fill, **kwargs: drawn_replacements.append(text),
    )

    _, applied_counts, _ = apply_replacements(
        Image.new("RGB", (200, 60), "white"),
        [{"text": "34 708 SM 2", "box": [[10, 10], [190, 10], [190, 35], [10, 35]]}],
        [{"reference": "34708SM", "replacement": "28"}],
        replacement_font_size=14,
    )

    assert applied_counts == [0]
    assert drawn_replacements == []


def test_replacement_respects_ocr_matches_for_each_line(monkeypatch) -> None:
    drawn_replacements: list[str] = []
    monkeypatch.setattr(
        image_replacement,
        "_draw_replacement_text",
        lambda draw, polygon, text, fill, **kwargs: drawn_replacements.append(text),
    )
    monkeypatch.setattr(
        image_replacement,
        "find_reference_occurrences",
        lambda text, reference: [(0, len(reference))],
    )

    _, applied_counts, _ = apply_replacements(
        Image.new("RGB", (200, 100), "white"),
        [
            {
                "text": "34708SM",
                "box": [[10, 10], [130, 10], [130, 35], [10, 35]],
                "matched_references": ["34708SM"],
            },
            {
                "text": "34708SM2",
                "box": [[10, 50], [150, 50], [150, 75], [10, 75]],
                "matched_references": [],
            },
        ],
        [{"reference": "34708SM", "replacement": "28"}],
        replacement_font_size=14,
    )

    assert applied_counts == [1]
    assert drawn_replacements == ["28"]


def test_replacement_segment_reduces_horizontal_width_by_one_more_pixel() -> None:
    polygon = image_replacement._replacement_segment(
        [[10, 10], [70, 10], [70, 30], [10, 30]],
        text_length=2,
        start_index=0,
        end_index=2,
    )

    assert polygon[0][0] == 11.5
    assert polygon[1][0] == 68.5


def test_replacement_mask_snaps_to_horizontal_when_text_does() -> None:
    polygon = image_replacement._fit_segment_to_visible_ink(
        [[10, 10], [70, 19], [67, 39], [7, 30]],
        (2, 18),
    )

    assert image_replacement.text_frame(polygon).angle == 0
    assert polygon[0][1] == polygon[1][1]
    assert polygon[2][1] == polygon[3][1]


def test_replacement_mask_keeps_angles_outside_snap_range() -> None:
    polygon = image_replacement._fit_segment_to_visible_ink(
        [[10, 10], [70, 23], [67, 43], [7, 30]],
        (2, 18),
    )

    assert image_replacement.text_frame(polygon).angle > 10


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


def test_replacement_mask_has_rounded_corners(monkeypatch) -> None:
    monkeypatch.setattr(
        image_replacement,
        "_sample_background_color",
        lambda image, polygon: (255, 0, 0),
    )
    monkeypatch.setattr(
        image_replacement,
        "_draw_replacement_text",
        lambda *args, **kwargs: None,
    )

    result, applied_counts, _ = apply_replacements(
        Image.new("RGB", (80, 40), "white"),
        [{"text": "R1", "box": [[10, 10], [70, 10], [70, 30], [10, 30]]}],
        [{"reference": "R1", "replacement": "7"}],
        replacement_font_size=14,
    )

    assert applied_counts == [1]
    assert result.getpixel((11, 11)) != (255, 0, 0)
    assert result.getpixel((15, 15)) == (255, 0, 0)


def test_replacement_preserves_thin_rule_at_bottom_of_text_box() -> None:
    source = Image.new("RGB", (80, 40), "white")
    draw = ImageDraw.Draw(source)
    draw.line((10, 10, 70, 10), fill="black", width=1)
    draw.line((10, 25, 70, 25), fill="black", width=1)
    draw.line((10, 29, 70, 29), fill="black", width=1)
    draw.line((10, 10, 10, 30), fill="black", width=1)
    draw.line((70, 10, 70, 30), fill="black", width=1)

    result, applied_counts, _ = apply_replacements(
        source,
        [{"text": "R1", "box": [[10, 10], [70, 10], [70, 30], [10, 30]]}],
        [{"reference": "R1", "replacement": "7"}],
        replacement_font_size=14,
    )

    assert applied_counts == [1]
    assert result.getpixel((12, 10)) == (0, 0, 0)
    assert result.getpixel((12, 25)) == (0, 0, 0)
    assert result.getpixel((12, 29)) == (0, 0, 0)
    assert result.getpixel((10, 15)) == (0, 0, 0)
    assert result.getpixel((70, 15)) == (0, 0, 0)


def test_replacement_fits_visible_text_bottom_and_preserves_rule(
    typography_sample, monkeypatch,
) -> None:
    source, polygon, _ = typography_sample(text="R1", size=24, padding=18)
    line_y = round(polygon[3][1]) - 4
    left = round(polygon[0][0]) + 2
    right = round(polygon[1][0]) - 2
    ImageDraw.Draw(source).line((left, line_y, right, line_y), fill="black")
    monkeypatch.setattr(
        image_replacement,
        "_draw_replacement_text",
        lambda *args, **kwargs: None,
    )

    result, applied_counts, _ = apply_replacements(
        source,
        [{"text": "R1", "box": polygon}],
        [{"reference": "R1", "replacement": "N1"}],
        replacement_font_size=14,
    )

    assert applied_counts == [1]
    assert result.getpixel(((left + right) // 2, line_y)) == (0, 0, 0)
    top, bottom = round(polygon[0][1]), round(polygon[3][1])
    assert all(
        result.getpixel((x, y))[0] >= 128
        for y in range(top, bottom)
        if y != line_y
        for x in range(round(polygon[0][0]), round(polygon[1][0]))
    )


def test_replacement_preserves_horizontal_rule_connected_to_glyph(
    typography_sample, monkeypatch,
) -> None:
    source, box, _ = typography_sample(text="R1", size=24, padding=18)
    candidate = image_replacement._replacement_segment(box, 2, 0, 2)
    background = image_replacement._sample_background_color(source, candidate)
    bounds = image_replacement.measure_character_bounds(source, candidate, background)
    assert bounds is not None
    line_y = round(candidate[0][1] + bounds[1] - 1)
    left, right = round(candidate[0][0]) + 1, round(candidate[1][0]) - 1
    ImageDraw.Draw(source).line((left, line_y, right, line_y), fill="black")
    monkeypatch.setattr(
        image_replacement,
        "_draw_replacement_text",
        lambda *args, **kwargs: None,
    )

    result, applied_counts, _ = apply_replacements(
        source,
        [{"text": "R1", "box": box}],
        [{"reference": "R1", "replacement": "N1"}],
        replacement_font_size=14,
    )

    assert applied_counts == [1]
    assert all(result.getpixel((x, line_y)) == (0, 0, 0) for x in range(left, right + 1))
