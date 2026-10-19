from __future__ import annotations

import base64
from io import BytesIO
from unittest.mock import MagicMock

import requests
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from lama_service.app import _crop_box_around_mask
from lama_service.app import app as lama_app


def test_inpaint_route_proxies_image_and_mask_to_lama(client: TestClient, monkeypatch, capsys) -> None:
    upstream_response = MagicMock()
    upstream_response.__enter__.return_value = upstream_response
    upstream_response.status_code = 200
    upstream_response.headers = {
        "content-type": "image/png",
        "server-timing": "inference_ms;dur=12.300",
        "x-lama-image-size": "1000x800",
        "x-lama-crop-size": "533x533",
        "x-lama-crop-box": "234,134,767,667",
    }
    upstream_response.content = b"synthetic-lama-result"
    monkeypatch.setattr("app.api.inpaint.requests.post", lambda *args, **kwargs: upstream_response)

    response = client.post(
        "/api/v1/image-processor/inpaint",
        files={
            "image": ("source.png", b"synthetic-image", "image/png"),
            "mask": ("mask.png", b"synthetic-mask", "image/png"),
        },
    )

    assert response.status_code == 200
    assert response.json()["edited_image"] == (
        f"data:image/png;base64,{base64.b64encode(b'synthetic-lama-result').decode('ascii')}"
    )
    logged_output = capsys.readouterr().out
    assert "image_inpaint_timing" in logged_output
    assert "inference_ms;dur=12.300" in logged_output


def test_inpaint_route_reports_unavailable_lama_service(client: TestClient, monkeypatch) -> None:
    def raise_connection_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError

    monkeypatch.setattr("app.api.inpaint.requests.post", raise_connection_error)
    response = client.post(
        "/api/v1/image-processor/inpaint",
        files={
            "image": ("source.png", b"synthetic-image", "image/png"),
            "mask": ("mask.png", b"synthetic-mask", "image/png"),
        },
    )

    assert response.status_code == 503
    assert "service LaMa n'est pas démarré" in response.json()["message"]


def test_lama_service_health_route() -> None:
    response = TestClient(lama_app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lama_service_inpaints_a_padded_mask_crop_and_preserves_other_pixels(monkeypatch) -> None:
    image_size = (1000, 800)
    source_image = Image.new("RGB", image_size, (20, 40, 60))
    image_bytes = BytesIO()
    source_image.save(image_bytes, format="PNG")

    mask = Image.new("L", image_size, 0)
    ImageDraw.Draw(mask).rectangle((490, 390, 510, 410), fill=255)
    mask_bytes = BytesIO()
    mask.save(mask_bytes, format="PNG")

    observed_crop_sizes: list[tuple[tuple[int, int], tuple[int, int]]] = []

    def fake_lama(crop_image: Image.Image, crop_mask: Image.Image) -> Image.Image:
        observed_crop_sizes.append((crop_image.size, crop_mask.size))
        padded_size = tuple(((dimension + 7) // 8) * 8 for dimension in crop_image.size)
        return Image.new("RGB", padded_size, (200, 50, 80))

    monkeypatch.setattr("lama_service.app.get_lama", lambda: fake_lama)

    response = TestClient(lama_app).post(
        "/inpaint",
        files={
            "image": ("source.png", image_bytes.getvalue(), "image/png"),
            "mask": ("mask.png", mask_bytes.getvalue(), "image/png"),
        },
    )

    assert response.status_code == 200, response.text
    assert observed_crop_sizes == [((533, 533), (533, 533))]
    assert response.headers["x-lama-image-size"] == "1000x800"
    assert response.headers["x-lama-crop-size"] == "533x533"
    assert response.headers["x-lama-crop-box"] == "234,134,767,667"
    assert "inference_ms;dur=" in response.headers["server-timing"]

    with Image.open(BytesIO(response.content)) as result:
        assert result.size == image_size
        assert result.convert("RGB").getpixel((500, 400)) == (200, 50, 80)
        assert result.convert("RGB").getpixel((489, 400)) == (20, 40, 60)
        assert result.convert("RGB").getpixel((0, 0)) == (20, 40, 60)


def test_lama_crop_padding_is_clamped_to_image_bounds() -> None:
    assert _crop_box_around_mask((1000, 800), (0, 0, 21, 21)) == (0, 0, 277, 277)


def test_lama_service_rejects_invalid_image_before_model_load() -> None:
    response = TestClient(lama_app).post(
        "/inpaint",
        files={
            "image": ("source.png", b"not-an-image", "image/png"),
            "mask": ("mask.png", b"not-a-mask", "image/png"),
        },
    )

    assert response.status_code == 400
