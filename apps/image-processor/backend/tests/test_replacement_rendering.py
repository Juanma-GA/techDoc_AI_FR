from __future__ import annotations

from math import atan2, degrees

import pytest
from PIL import Image, ImageChops

from app.services.replacement_rendering import _draw_replacement_text, _histogram_median
from app.services.text_geometry import snapped_angle, text_frame


def _ink(image):
    difference = ImageChops.difference(image, Image.new("RGB", image.size, "white"))
    box = difference.getbbox()
    assert box is not None
    return difference.crop(box)


@pytest.mark.parametrize(
    ("angle", "expected"),
    [
        (0, 0), (-9.99, 0), (9.99, 0), (-10, 0), (10, 0), (10.01, 10.01), (17, 17),
        (80, 90), (100, 90), (175, 180), (-91, -90),
    ],
)
def test_angles_within_ten_degrees_of_an_axis_are_snapped(angle, expected):
    assert snapped_angle(angle) == pytest.approx(expected)


@pytest.mark.parametrize(("angle", "axis"), [(9.9, 0), (-9.9, 0), (91, 90), (176, 180), (-89, -90)])
def test_rendered_text_has_no_spurious_small_slant(typography_sample, angle, axis):
    _, polygon, _ = typography_sample(text="R123456789", size=32, angle=angle)
    result = Image.new("RGB", (400, 300), "white")
    assert _draw_replacement_text(result, polygon, "123456789", (0, 0, 0), font_size=24) == 24
    _, axis_polygon, _ = typography_sample(text="R123456789", size=32, angle=axis)
    expected = Image.new("RGB", result.size, "white")
    _draw_replacement_text(expected, axis_polygon, "123456789", (0, 0, 0), font_size=24)
    assert _ink(result).size == _ink(expected).size
    assert _ink(result).tobytes() == _ink(expected).tobytes()


@pytest.mark.parametrize("angle", [17, -31, 90, -90, 145])
def test_real_rotations_are_kept_and_text_stays_centered(typography_sample, angle):
    _, polygon, _ = typography_sample(text="R123456789", size=32, angle=angle)
    result = Image.new("RGB", (400, 300), "white")
    _draw_replacement_text(result, polygon, "123456789", (0, 0, 0), font_size=24)
    ink = ImageChops.difference(result, Image.new("RGB", result.size, "white")).convert("L")
    points = [
        (x, y) for y in range(result.height) for x in range(result.width) if ink.getpixel((x, y)) >= 128
    ]
    center_x = sum(x for x, _ in points) / len(points)
    center_y = sum(y for _, y in points) / len(points)
    xx = sum((x - center_x) ** 2 for x, _ in points)
    yy = sum((y - center_y) ** 2 for _, y in points)
    xy = sum((x - center_x) * (y - center_y) for x, y in points)
    measured_angle = degrees(atan2(2 * xy, xx - yy)) / 2
    error = (measured_angle - angle + 90) % 180 - 90
    assert abs(error) <= 1.5
    bounds = ink.getbbox()
    assert bounds is not None
    frame = text_frame(polygon)
    assert abs((bounds[0] + bounds[2]) / 2 - frame.center[0]) <= 2
    assert abs((bounds[1] + bounds[3]) / 2 - frame.center[1]) <= 2


def test_font_size_only_shrinks_if_the_replacement_is_too_wide():
    polygon = [[20, 40], [100, 40], [100, 80], [20, 80]]
    normal = Image.new("RGB", (200, 120), "white")
    assert _draw_replacement_text(normal, polygon, "12", (0, 0, 0), font_size=24) == 24
    wide = Image.new("RGB", normal.size, "white")
    fitted = _draw_replacement_text(wide, polygon, "1234567890", (0, 0, 0), font_size=24)
    assert 1 <= fitted < 24
    assert _ink(wide).width <= 73


def test_vertical_fit_uses_the_reading_width_not_axis_aligned_bbox():
    polygon = [[100, 20], [100, 200], [70, 200], [70, 20]]
    image = Image.new("RGB", (200, 240), "white")
    assert _draw_replacement_text(image, polygon, "1234567890", (0, 0, 0), font_size=24) == 24


def test_background_histogram_preserves_even_and_odd_median():
    histogram = [0] * 256
    histogram[10] = histogram[20] = 1
    assert _histogram_median(histogram) == 15
    histogram[20] += 1
    assert _histogram_median(histogram) == 20
