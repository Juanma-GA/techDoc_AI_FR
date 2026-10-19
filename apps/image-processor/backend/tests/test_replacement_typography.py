from __future__ import annotations

import pytest
from fastapi import HTTPException
from PIL import Image, ImageChops, ImageDraw

from app.services.image_replacement import apply_replacements
from app.services.replacement_typography import (
    dominant_height,
    font_size_for_height,
    load_replacement_font,
    measure_character_height,
)


@pytest.mark.parametrize("angle", [0, 4.9, 17, -37, 90, 180, -90])
@pytest.mark.parametrize("padding", [8, 28])
def test_measures_visible_characters_not_ocr_box_height(typography_sample, angle, padding):
    image, polygon, expected = typography_sample(angle=angle, padding=padding)
    measured = measure_character_height(image, polygon, (255, 255, 255))
    assert measured is not None
    assert abs(measured - expected) <= 2


def test_measurement_discards_specks_and_a_thin_border_line(typography_sample):
    image, polygon, expected = typography_sample(padding=28)
    left, top = (round(value) for value in polygon[0])
    bottom = round(polygon[3][1])
    ImageDraw.Draw(image).line((left + 2, top, left + 2, bottom), fill="black")
    image.putpixel((left + 10, top + 4), (0, 0, 0))
    measured = measure_character_height(image, polygon, (255, 255, 255))
    assert measured is not None
    assert abs(measured - expected) <= 1


def test_no_ink_is_not_reported_as_a_valid_character_height(typography_sample):
    image, polygon, _ = typography_sample()
    image.paste("white", (0, 0, image.width, image.height))
    assert measure_character_height(image, polygon, (255, 255, 255)) is None
    with pytest.raises(HTTPException) as error:
        dominant_height([])
    assert error.value.status_code == 422


def test_dominant_size_is_the_mean_of_the_most_frequent_group_not_all_sizes():
    assert dominant_height([18, 18, 20, 19, 50, 55]) == 18.75
    assert dominant_height([20, 10, 20, 10]) == 10
    assert dominant_height([22, 20, 21, 80]) == 21


@pytest.mark.parametrize("height", [8, 17, 18.75, 40, 100])
def test_font_size_matches_the_target_visible_height(height):
    size = font_size_for_height(height)
    box = load_replacement_font(size).getbbox("H0")
    assert abs(box[3] - box[1] - height) <= 1


def test_replacements_share_dominant_font_size_and_ignore_unselected_title(typography_sample):
    source = Image.new("RGB", (2000, 300), "white")
    lines = []
    pairs = []
    for index, size in enumerate([24, 25, 24, 48, 80]):
        text = f"R{index + 1}" if index < 4 else "TITLE"
        image, polygon, _ = typography_sample(text=text, size=size)
        source.paste(image, (400 * index, 0))
        lines.append({"text": text, "box": [[x + 400 * index, y] for x, y in polygon]})
        if index < 4:
            pairs.append({"reference": text, "replacement": f"10{index + 1}"})
    result, counts, size = apply_replacements(source, lines, pairs)
    assert counts == [1, 1, 1, 1]
    assert size is not None
    cap_box = load_replacement_font(size).getbbox("H0")
    assert 16 <= cap_box[3] - cap_box[1] <= 19
    heights = []
    for index in range(4):
        tile = result.crop((400 * index, 0, 400 * (index + 1), 300))
        bounds = ImageChops.difference(tile, Image.new("RGB", tile.size, "white")).getbbox()
        assert bounds is not None
        heights.append(bounds[3] - bounds[1])
    assert max(heights) - min(heights) <= 1
    assert result.crop((1600, 0, 2000, 300)).tobytes() == source.crop((1600, 0, 2000, 300)).tobytes()


def test_missing_pixels_produce_an_explicit_error_without_inventing_a_font_size():
    source = Image.new("RGB", (100, 60), "white")
    with pytest.raises(HTTPException) as error:
        apply_replacements(
            source,
            [{"text": "R1", "box": [[10, 10], [80, 10], [80, 40], [10, 40]]}],
            [{"reference": "R1", "replacement": "1"}],
        )
    assert error.value.status_code == 422
