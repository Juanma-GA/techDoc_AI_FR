"""Ingestion universelle -> PDF fidele : passthrough PDF, formats, extraction zip."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.core import ingest
from app.core.errors import AppError


def test_to_pdf_bytes_pdf_passthrough(sample_pdf_bytes: bytes) -> None:
    out, name = ingest.to_pdf_bytes("manual.pdf", sample_pdf_bytes)
    assert out == sample_pdf_bytes  # zero conversion pour un PDF natif
    assert name == "manual.pdf"


def test_to_pdf_bytes_rejects_unsupported() -> None:
    with pytest.raises(AppError) as exc:
        ingest.to_pdf_bytes("notes.txt", b"hello")
    assert exc.value.code == "UNSUPPORTED_FORMAT"


def test_to_pdf_bytes_rejects_bad_pdf() -> None:
    with pytest.raises(AppError) as exc:
        ingest.to_pdf_bytes("fake.pdf", b"not a pdf")
    assert exc.value.code == "UPLOAD_BAD_EXT"


def test_expand_uploads_zip_keeps_supported_ignores_rest(sample_pdf_bytes: bytes) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.pdf", sample_pdf_bytes)
        z.writestr("readme.txt", b"nope")
    files, ignored = ingest.expand_uploads([("bundle.zip", buf.getvalue())])
    assert [n for n, _ in files] == ["a.pdf"]
    assert any("readme.txt" in i for i in ignored)


def test_expand_uploads_empty_raises() -> None:
    with pytest.raises(AppError) as exc:
        ingest.expand_uploads([("readme.txt", b"nope")])
    assert exc.value.code == "NO_SUPPORTED_FILE"
