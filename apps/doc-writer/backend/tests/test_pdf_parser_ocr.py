"""pdf_parser : cascade couche texte native -> vision -> OCR document -> local.

- couche texte exploitable -> utilisee directement (ni vision ni OCR) ;
- pas de couche texte (PDF image) + client -> vision, puis repli OCR ;
- pas de client -> extraction locale.

Aucun appel reseau : les clients Mistral sont des faux (stub).
"""

from __future__ import annotations

import tempfile

import fitz  # type: ignore[import-untyped]

from app.parsers import pdf_parser


def _pdf_with_text(text: str) -> str:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    f = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    f.close()
    doc.save(f.name)
    doc.close()
    return f.name


def _pdf_blank() -> str:
    """PDF d'une page SANS couche texte (simule un PDF image / scan)."""
    doc = fitz.open()
    doc.new_page()
    f = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    f.close()
    doc.save(f.name)
    doc.close()
    return f.name


class _FakeMistral:
    """Faux client : `vision` / `ocr` controlent le texte renvoye par chaque
    niveau (ou une Exception a lever)."""

    def __init__(self, vision="", ocr=""):
        self._vision = vision
        self._ocr = ocr

    def vision_extract(self, images_png, **_kw):  # noqa: ANN001, ARG002
        if isinstance(self._vision, Exception):
            raise self._vision
        return self._vision

    def ocr_pdf(self, pdf_bytes, **_kw):  # noqa: ANN001, ARG002
        if isinstance(self._ocr, Exception):
            raise self._ocr
        return self._ocr


def test_native_text_used_when_sufficient_no_vision_call():
    # Couche texte dense -> utilisee directement, la vision ne doit PAS servir.
    path = _pdf_with_text("Experience professionnelle data et IA. " * 8)
    out = pdf_parser.parse(path, mistral=_FakeMistral(vision="NE DOIT PAS APPARAITRE"))
    assert "NE DOIT PAS APPARAITRE" not in out["text"]
    assert "Experience professionnelle" in out["text"]


def test_vision_used_when_no_text_layer():
    path = _pdf_blank()  # PDF image -> couche texte vide -> vision
    out = pdf_parser.parse(path, mistral=_FakeMistral(vision="TRANSCRIPTION VISION"))
    assert out["text"] == "TRANSCRIPTION VISION"


def test_ocr_fallback_when_vision_empty_on_image():
    path = _pdf_blank()
    out = pdf_parser.parse(path, mistral=_FakeMistral(vision="", ocr="TEXTE OCR"))
    assert out["text"] == "TEXTE OCR"


def test_local_fallback_when_no_client_and_image():
    path = _pdf_blank()
    out = pdf_parser.parse(path)  # pas de client, page vide -> local (Tesseract absent OK)
    assert isinstance(out["text"], str)


def test_native_text_used_without_client():
    path = _pdf_with_text("Ingenieur Data. Langues Anglais Espagnol. " * 6)
    out = pdf_parser.parse(path)
    assert "Ingenieur Data" in out["text"]
