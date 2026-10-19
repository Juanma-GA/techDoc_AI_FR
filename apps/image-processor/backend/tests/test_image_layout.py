from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.services.constants import A4_DPI, A4_HEIGHT, A4_WIDTH
from app.services.image_layout import create_a4_page, export_jpeg, output_filename, prepare_source_image


def test_landscape_image_is_centered_on_a4_portrait_page() -> None:
    source = Image.new("RGB", (120, 60), (12, 34, 56))

    page, scale_x, scale_y, left, top = create_a4_page(source)

    assert page.size == (A4_WIDTH, A4_HEIGHT)
    assert left == 0
    assert top > 0
    assert scale_x == scale_y
    assert page.getpixel((10, 10)) == (255, 255, 255)
    assert page.getpixel((A4_WIDTH // 2, A4_HEIGHT // 2)) == (12, 34, 56)


def test_transparent_image_is_flattened_on_white() -> None:
    source = Image.new("RGBA", (120, 60), (12, 34, 56, 0))

    page, _, _, _, top = create_a4_page(source)

    assert page.getpixel((A4_WIDTH // 2, top + 5)) == (255, 255, 255)


def test_exif_orientation_is_normalized_before_ocr() -> None:
    raw_image = Image.new("RGB", (60, 120), "white")
    exif = Image.Exif()
    exif[274] = 6
    encoded = BytesIO()
    raw_image.save(encoded, format="JPEG", exif=exif)

    normalized_image, normalized_bytes = prepare_source_image(encoded.getvalue())

    assert normalized_image.size == (120, 60)
    with Image.open(BytesIO(normalized_bytes)) as ocr_image:
        assert ocr_image.size == (120, 60)
        assert ocr_image.getexif().get(274) is None


def test_output_filename_uses_icn_or_image_stem() -> None:
    assert output_filename("source.png", "ICN-01") == "ICN-01.jpg"
    assert output_filename("source.png", "ICN-01.jpg") == "ICN-01.jpg"
    assert output_filename("source.png", "ICN-01.JPEG") == "ICN-01.jpg"
    assert output_filename("source.png", "ICN:01") == "ICN_01.jpg"
    assert output_filename("source.png", None) == "source-modifiee.jpg"


def test_a4_output_is_jpeg_with_300_dpi_metadata() -> None:
    image = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
    encoded = BytesIO()
    image.save(encoded, format="JPEG", dpi=(A4_DPI, A4_DPI))

    with Image.open(BytesIO(encoded.getvalue())) as result:
        assert result.format == "JPEG"
        assert result.size == (A4_WIDTH, A4_HEIGHT)
        assert result.info["dpi"] == (A4_DPI, A4_DPI)


def test_download_does_not_reencode_an_existing_print_ready_jpeg() -> None:
    source = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (12, 34, 56))
    encoded = BytesIO()
    source.save(encoded, format="JPEG", quality=95, dpi=(A4_DPI, A4_DPI))
    contents = encoded.getvalue()
    assert export_jpeg(contents) == contents
