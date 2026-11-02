"""Conversions avec le VRAI Microsoft Word du poste (opt-in).

A lancer sur un poste Windows avec Word (Microsoft 365) :

    set DR_TEST_REAL_WORD=1
    set WORD_SENSITIVITY_LABEL_ID=<GUID de l'etiquette choisie par l'IT>
    python -m pytest tests/test_word_real.py -v

Hors de ce cadre (poste sans Word), les tests sont ignores.
"""

from __future__ import annotations

import io
import os
import zipfile

import fitz
import pytest

from app.config import settings
from app.core import doc_convert
from app.parsers.pdf_parser import parse_pdf

pytestmark = [
    pytest.mark.requires_office,
    pytest.mark.skipif(
        os.environ.get("DR_TEST_REAL_WORD") != "1" or not doc_convert.word_available(),
        reason="opt-in : DR_TEST_REAL_WORD=1 sur un poste avec Microsoft Word",
    ),
]

TEXT = "Faulty parts should be replaced by approved spares only."
MASS = "400 g + 3% (0,882 lb + 3%)"


@pytest.fixture(autouse=True)
def _word_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "office_converter", "word")
    label = os.environ.get("WORD_SENSITIVITY_LABEL_ID", settings.word_sensitivity_label_id)
    monkeypatch.setattr(settings, "word_sensitivity_label_id", label)


def _label_of(docx: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(docx)) as archive:
        names = [n for n in archive.namelist() if n.endswith("LabelInfo.xml") or n == "docProps/custom.xml"]
        return " ".join(archive.read(n).decode("utf-8", "replace") for n in names)


def _text_of_docx(docx: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(docx)) as archive:
        return archive.read("word/document.xml").decode("utf-8", "replace")


def _pdf_text(pdf: bytes, tmp_path) -> str:
    path = tmp_path / "out.pdf"
    path.write_bytes(pdf)
    return parse_pdf(path).full_text


@pytest.fixture(scope="module")
def source_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), TEXT, fontname="helv", fontsize=11)
    page.insert_text((72, 130), f"Mass: {MASS}.", fontname="helv", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="module")
def source_docx(source_pdf: bytes) -> bytes:
    """Un .docx produit par Word lui-meme (PDF -> .docx), donc etiquete."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "office_converter", "word")
        mp.setattr(settings, "word_sensitivity_label_id",
                   os.environ.get("WORD_SENSITIVITY_LABEL_ID", settings.word_sensitivity_label_id))
        return doc_convert.pdf_to_docx_bytes(source_pdf)


@pytest.fixture(scope="module")
def source_doc(source_docx: bytes) -> bytes:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "office_converter", "word")
        return doc_convert.docx_to_doc_bytes(source_docx)


def test_pdf_to_docx_is_labelled_and_keeps_the_text(source_docx: bytes) -> None:
    assert source_docx[:2] == b"PK"
    assert "approved spares" in _text_of_docx(source_docx)
    if settings.word_sensitivity_label_id:
        assert settings.word_sensitivity_label_id in _label_of(source_docx)


def test_docx_to_doc_is_a_legacy_word_file(source_doc: bytes) -> None:
    assert source_doc[:8] == bytes.fromhex("D0CF11E0A1B11AE1")  # OLE2 (Word 97-2003)


def test_doc_to_docx_with_label(source_doc: bytes) -> None:
    docx, engine = doc_convert.office_to_docx_bytes(source_doc, ".doc")
    assert engine == "word"
    assert "approved spares" in _text_of_docx(docx)
    if settings.word_sensitivity_label_id:
        assert settings.word_sensitivity_label_id in _label_of(docx)


def test_doc_to_pdf(source_doc: bytes, tmp_path) -> None:
    pdf, engine = doc_convert.doc_to_pdf_bytes(source_doc, ".doc")
    assert engine == "word" and pdf.startswith(b"%PDF")
    assert TEXT in _pdf_text(pdf, tmp_path)


def test_docx_to_pdf(source_docx: bytes, tmp_path) -> None:
    pdf, engine = doc_convert.doc_to_pdf_bytes(source_docx, ".docx")
    assert engine == "word"
    text = _pdf_text(pdf, tmp_path)
    assert TEXT in text and MASS in text


def test_pdf_to_doc(source_pdf: bytes) -> None:
    data = doc_convert.pdf_to_doc_bytes(source_pdf)
    assert data[:8] == bytes.fromhex("D0CF11E0A1B11AE1")


def test_real_word_instance_has_macros_disabled_before_opening() -> None:
    """Le vrai Word accepte le reglage « macros desactivees » et le garde
    jusqu'a l'ouverture du document."""
    seen: dict[str, int] = {}
    original = doc_convert._open_untrusted

    def spy(word, src):
        seen["security"] = word.AutomationSecurity
        return original(word, src)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(doc_convert, "_open_untrusted", spy)
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "x")
        pdf = doc.tobytes()
        doc.close()
        doc_convert.pdf_to_doc_bytes(pdf)
    assert seen["security"] == 3


_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")
_CSRF = {"X-Requested-With": "doc-reviewer"}


def test_api_doc_upload_and_every_export(client, source_doc: bytes) -> None:
    """Parcours utilisateur reel : un .doc est televerse, revu en Word natif, puis
    exporte en .doc, .docx et PDF, sans LibreOffice."""
    up = client.post(
        "/api/v1/documents",
        files={"file": ("manual.doc", source_doc, "application/msword")},
        headers=_CSRF,
    )
    assert up.status_code == 201, up.text
    doc = up.json()
    assert (doc["source_format"], doc["working_format"]) == ("doc", "docx")

    exports = client.get(f"/api/v1/documents/{doc['id']}/exports").json()["available"]
    assert {(e["kind"], e["format"]) for e in exports} >= {
        ("original", "doc"), ("commented", "pdf"), ("converted", "doc"),
    }

    as_doc = client.get(f"/api/v1/documents/{doc['id']}/export", params={"format": "doc"})
    assert as_doc.status_code == 200 and as_doc.content[:8] == _OLE2
    as_pdf = client.get(f"/api/v1/documents/{doc['id']}/export", params={"format": "pdf"})
    assert as_pdf.status_code == 200 and as_pdf.content[:5] == b"%PDF-"
    commented = client.get(f"/api/v1/documents/{doc['id']}/export", params={"format": "commented"})
    assert commented.status_code == 200 and commented.content[:5] == b"%PDF-"
    as_docx = client.get(f"/api/v1/documents/{doc['id']}/export", params={"format": "docx"})
    assert as_docx.status_code == 200 and as_docx.content[:2] == b"PK"


def test_api_pdf_upload_converted_exports(client, source_pdf: bytes) -> None:
    up = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", source_pdf, "application/pdf")},
        headers=_CSRF,
    )
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]
    as_docx = client.get(f"/api/v1/documents/{doc_id}/export", params={"format": "docx"})
    assert as_docx.status_code == 200 and as_docx.content[:2] == b"PK"
    if settings.word_sensitivity_label_id:
        assert settings.word_sensitivity_label_id in _label_of(as_docx.content)
    as_doc = client.get(f"/api/v1/documents/{doc_id}/export", params={"format": "doc"})
    assert as_doc.status_code == 200 and as_doc.content[:8] == _OLE2


def test_watchdog_stops_a_stuck_real_word(source_doc: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    """Une conversion bloquee (simulee : Word ne repond plus pendant 8 s) est
    arretee par le garde-fou au bout du delai, sans nouvel essai, et l'appelant
    recoit une erreur claire au lieu d'attendre indefiniment."""
    import time

    monkeypatch.setattr(settings, "word_convert_timeout_seconds", 3)
    original = doc_convert._open_untrusted
    started: list[float] = []

    def stuck(word, src):
        started.append(time.monotonic())
        time.sleep(8)
        return original(word, src)  # Word a ete arrete entre-temps : l'appel COM echoue

    monkeypatch.setattr(doc_convert, "_open_untrusted", stuck)
    begin = time.monotonic()
    with pytest.raises(doc_convert.AppError) as err:
        doc_convert.doc_to_pdf_bytes(source_doc, ".doc")
    assert len(started) == 1  # pas de nouvel essai apres un arret par le garde-fou
    assert "garde-fou" in str(err.value.detail)
    assert time.monotonic() - begin < 30


def test_no_word_process_is_left_behind() -> None:
    import subprocess

    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE", "/V", "/FO", "CSV"],
        capture_output=True, text=True, check=False,
    ).stdout
    assert "doc-reviewer-" not in out
