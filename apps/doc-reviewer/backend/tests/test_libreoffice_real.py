"""Conversions avec le VRAI LibreOffice du poste (opt-in), moteur seul
(`OFFICE_CONVERTER=libreoffice`, edition « LibreOffice » du guide d'installation).

A lancer sur un poste avec LibreOffice (installe, ou portable via DR_SOFFICE_PATH) :

    set DR_TEST_REAL_LIBREOFFICE=1
    python -m pytest tests/test_libreoffice_real.py -v

Hors de ce cadre (poste sans LibreOffice), les tests sont ignores.
"""

from __future__ import annotations

import io
import os
import zipfile

import docx
import fitz
import pytest

from app.config import settings
from app.core import doc_convert
from app.parsers.pdf_parser import parse_pdf

pytestmark = pytest.mark.skipif(
    os.environ.get("DR_TEST_REAL_LIBREOFFICE") != "1" or not doc_convert._find_soffice(),
    reason="opt-in : DR_TEST_REAL_LIBREOFFICE=1 sur un poste avec LibreOffice",
)

TEXT = "Faulty parts should be replaced by approved spares only."
_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")
_CSRF = {"X-Requested-With": "doc-reviewer"}


@pytest.fixture(autouse=True)
def _libreoffice_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "office_converter", "libreoffice")


def _text_of_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8", "replace")


@pytest.fixture(scope="module")
def source_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), TEXT, fontname="helv", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="module")
def source_docx() -> bytes:
    document = docx.Document()
    document.add_paragraph(TEXT)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def source_doc(source_docx: bytes) -> bytes:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "office_converter", "libreoffice")
        return doc_convert.docx_to_doc_bytes(source_docx)


def test_docx_to_doc_is_a_legacy_word_file(source_doc: bytes) -> None:
    assert source_doc[:8] == _OLE2


def test_doc_to_docx(source_doc: bytes) -> None:
    data, engine = doc_convert.office_to_docx_bytes(source_doc, ".doc")
    assert engine == "libreoffice"
    assert "approved spares" in _text_of_docx(data)


def test_doc_and_docx_to_pdf(source_doc: bytes, source_docx: bytes, tmp_path) -> None:
    for data, suffix in ((source_doc, ".doc"), (source_docx, ".docx")):
        pdf, engine = doc_convert.doc_to_pdf_bytes(data, suffix)
        assert engine == "libreoffice" and pdf.startswith(b"%PDF")
        path = tmp_path / f"out{suffix}.pdf"
        path.write_bytes(pdf)
        assert TEXT in parse_pdf(path).full_text


def test_pdf_to_docx_keeps_the_text(source_pdf: bytes) -> None:
    """Un PDF s'ouvre dans Draw par defaut (aucun export .docx) : l'import
    Writer doit etre force."""
    data = doc_convert.pdf_to_docx_bytes(source_pdf)
    assert data[:2] == b"PK"
    assert "approved spares" in _text_of_docx(data)


def test_pdf_to_doc(source_pdf: bytes) -> None:
    assert doc_convert.pdf_to_doc_bytes(source_pdf)[:8] == _OLE2


def test_api_doc_upload_and_every_export(client, source_doc: bytes) -> None:
    up = client.post(
        "/api/v1/documents",
        files={"file": ("manual.doc", source_doc, "application/msword")},
        headers=_CSRF,
    )
    assert up.status_code == 201, up.text
    doc = up.json()
    assert (doc["source_format"], doc["working_format"]) == ("doc", "docx")
    for fmt, magic in (("doc", _OLE2), ("pdf", b"%PDF-"), ("commented", b"%PDF-"), ("docx", b"PK")):
        res = client.get(f"/api/v1/documents/{doc['id']}/export", params={"format": fmt})
        assert res.status_code == 200 and res.content.startswith(magic), (fmt, res.status_code)


def test_api_pdf_upload_converted_exports(client, source_pdf: bytes) -> None:
    up = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", source_pdf, "application/pdf")},
        headers=_CSRF,
    )
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]
    for fmt, magic in (("docx", b"PK"), ("doc", _OLE2)):
        res = client.get(f"/api/v1/documents/{doc_id}/export", params={"format": fmt})
        assert res.status_code == 200 and res.content.startswith(magic), (fmt, res.status_code)
