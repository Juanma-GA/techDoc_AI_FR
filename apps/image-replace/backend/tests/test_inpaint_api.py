from __future__ import annotations

import base64
from unittest.mock import MagicMock

import requests
from fastapi.testclient import TestClient

from lama_service.app import app as lama_app


def test_inpaint_route_proxies_image_and_mask_to_lama(client: TestClient, monkeypatch) -> None:
    upstream_response = MagicMock()
    upstream_response.__enter__.return_value = upstream_response
    upstream_response.status_code = 200
    upstream_response.headers = {"content-type": "image/png"}
    upstream_response.content = b"synthetic-lama-result"
    monkeypatch.setattr("app.api.inpaint.requests.post", lambda *args, **kwargs: upstream_response)

    response = client.post(
        "/api/v1/image-replace/inpaint",
        files={
            "image": ("source.png", b"synthetic-image", "image/png"),
            "mask": ("mask.png", b"synthetic-mask", "image/png"),
        },
    )

    assert response.status_code == 200
    assert response.json()["edited_image"] == (
        f"data:image/png;base64,{base64.b64encode(b'synthetic-lama-result').decode('ascii')}"
    )


def test_inpaint_route_reports_unavailable_lama_service(client: TestClient, monkeypatch) -> None:
    def raise_connection_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError

    monkeypatch.setattr("app.api.inpaint.requests.post", raise_connection_error)
    response = client.post(
        "/api/v1/image-replace/inpaint",
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


def test_lama_service_rejects_invalid_image_before_model_load() -> None:
    response = TestClient(lama_app).post(
        "/inpaint",
        files={
            "image": ("source.png", b"not-an-image", "image/png"),
            "mask": ("mask.png", b"not-a-mask", "image/png"),
        },
    )

    assert response.status_code == 400
