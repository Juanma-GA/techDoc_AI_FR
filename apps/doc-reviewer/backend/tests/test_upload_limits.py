"""Uploads : lecture bornee par MAX_UPLOAD_SIZE_MB et endpoints bloquants
executes hors de la boucle asynchrone."""

from __future__ import annotations

import inspect
import io

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.errors import AppError


# ---------------------------------------------------------------------------
# Uploads : lecture bornee + endpoints bloquants hors boucle asynchrone
# ---------------------------------------------------------------------------


class _CountingFile(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.bytes_read = 0

    def read(self, size: int | None = -1) -> bytes:  # type: ignore[override]
        chunk = super().read(size)
        self.bytes_read += len(chunk)
        return chunk


def test_read_upload_limited_stops_reading_past_the_limit() -> None:
    from fastapi import UploadFile

    from app.core.security import _READ_CHUNK, read_upload_limited

    limit = 2 * _READ_CHUNK
    payload = _CountingFile(b"x" * (20 * _READ_CHUNK))
    upload = UploadFile(file=payload, filename="huge.pdf")
    with pytest.raises(AppError) as excinfo:
        read_upload_limited(upload, limit)
    assert excinfo.value.code == "FILE_TOO_LARGE"
    assert excinfo.value.status_code == 413
    assert payload.bytes_read <= limit + _READ_CHUNK

    small = UploadFile(file=io.BytesIO(b"abc"), filename="ok.pdf")
    assert read_upload_limited(small, limit) == b"abc"


def test_oversized_upload_is_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    big = b"%PDF-1.4\n" + b"0" * (2 * 1024 * 1024)
    response = client.post("/api/v1/documents", files={"file": ("big.pdf", big, "application/pdf")})
    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"
    response = client.post(
        "/api/v1/rules/inspect",
        files={"file": ("big.xlsx", big, "application/octet-stream")},
    )
    assert response.status_code == 413


def test_blocking_upload_endpoints_run_in_threadpool() -> None:
    """Conversion LibreOffice/Word et appels Mistral synchrones : un `async def`
    les executait SUR la boucle evenementielle et figeait toute l'application."""
    from app.api import rules

    for endpoint in (rules.inspect_checklist, rules.import_checklist, rules.suggest_rules_from_files):
        assert not inspect.iscoroutinefunction(endpoint), endpoint.__name__
