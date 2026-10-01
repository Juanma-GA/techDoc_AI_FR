"""Synthetic tests for upload size checks before application-level reads."""

import asyncio
from io import BytesIO

import pytest
from starlette.datastructures import UploadFile

from app.core.errors import AppError
from app.core.security import read_upload_bounded, read_upload_bounded_async


class TrackingFile(BytesIO):
    def __init__(self, value: bytes) -> None:
        super().__init__(value)
        self.read_calls = 0

    def read(self, size: int = -1) -> bytes:
        self.read_calls += 1
        return super().read(size)


def test_sync_upload_rejects_known_oversize_before_reading() -> None:
    stream = TrackingFile(b"SYNTHETIC-OVERSIZE")
    upload = UploadFile(filename="synthetic.pdf", file=stream, size=len(stream.getvalue()))

    with pytest.raises(AppError) as exc_info:
        read_upload_bounded(upload, 4)

    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert stream.read_calls == 0


def test_async_upload_rejects_known_oversize_before_reading() -> None:
    stream = TrackingFile(b"SYNTHETIC-OVERSIZE")
    upload = UploadFile(filename="synthetic.xlsx", file=stream, size=len(stream.getvalue()))

    with pytest.raises(AppError) as exc_info:
        asyncio.run(read_upload_bounded_async(upload, 4))

    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert stream.read_calls == 0


def test_upload_within_limit_is_read_completely() -> None:
    upload = UploadFile(
        filename="synthetic.pdf",
        file=BytesIO(b"SYNTHETIC"),
        size=len(b"SYNTHETIC"),
    )

    assert read_upload_bounded(upload, len(b"SYNTHETIC")) == b"SYNTHETIC"