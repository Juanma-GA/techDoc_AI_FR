"""Parseur PDF (`app.parsers.pdf_parser`) : couche texte + repli OCR.

Deterministe :
- un PDF natif (couche texte) est extrait directement ;
- un PDF image-only (scan simule) n'a PAS de couche texte ;
- sans Tesseract : l'OCR degrade proprement (page vide, pas de crash) ;
- avec Tesseract (skip sinon) : l'OCR recupere le texte de l'image.
"""

from __future__ import annotations

import os
import tempfile

import fitz  # type: ignore[import-untyped]
import pytest

from app.config import settings
from app.parsers import pdf_parser


def _ocr_available() -> bool:
    """L'OCR PyMuPDF est exploitable si un dossier tessdata (avec au moins un
    pack `.traineddata`) est pointe par `pdf_ocr_tessdata` ou `TESSDATA_PREFIX`.
    On ne se fie PAS au binaire `tesseract` sur le PATH : PyMuPDF lit tessdata
    directement."""
    prefix = settings.pdf_ocr_tessdata or os.environ.get("TESSDATA_PREFIX", "")
    if not prefix or not os.path.isdir(prefix):
        return False
    return any(f.endswith(".traineddata") for f in os.listdir(prefix))


_OCR_AVAILABLE = _ocr_available()


def _text_pdf(path: str, text: str) -> None:
    """PDF natif avec une vraie couche texte (via reportlab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica", 40)
    c.drawString(100, 700, text)
    c.save()


def _image_only_pdf(src_pdf: str, out_pdf: str) -> None:
    """Rend la 1re page d'un PDF en image et la replace dans un PDF sans couche
    texte : simule un document scanne."""
    with fitz.open(src_pdf) as src:
        page = src[0]
        pix = page.get_pixmap(dpi=200)
        rect = page.rect
    out = fitz.open()
    npage = out.new_page(width=rect.width, height=rect.height)
    npage.insert_image(npage.rect, pixmap=pix)
    out.save(out_pdf)
    out.close()


@pytest.fixture()
def pdfs():
    d = tempfile.mkdtemp(prefix="docwriter_pdf_ocr_")
    native = os.path.join(d, "native.pdf")
    scanned = os.path.join(d, "scanned.pdf")
    _text_pdf(native, "BONJOUR OCR 12345")
    _image_only_pdf(native, scanned)
    yield {"native": native, "scanned": scanned}


def test_native_pdf_text_is_extracted(pdfs) -> None:
    out = pdf_parser.parse(pdfs["native"])
    assert "BONJOUR OCR 12345" in out["text"]


def test_image_pdf_has_no_text_layer(pdfs) -> None:
    # Sanity : le PDF image-only n'expose aucune couche texte.
    with fitz.open(pdfs["scanned"]) as doc:
        assert doc[0].get_text("text").strip() == ""


@pytest.mark.skipif(_OCR_AVAILABLE, reason="tessdata present : l'OCR aboutit")
def test_image_pdf_degrades_gracefully_without_ocr(pdfs) -> None:
    # OCR active mais tessdata absent -> pas de crash, texte vide.
    out = pdf_parser.parse(pdfs["scanned"])
    assert out["text"] == ""


@pytest.mark.skipif(not _OCR_AVAILABLE, reason="tessdata absent : OCR non testable")
def test_image_pdf_ocr_recovers_text(pdfs) -> None:
    out = pdf_parser.parse(pdfs["scanned"])
    # OCR best-effort : on tolere le bruit, on verifie qu'un token ressort.
    assert "OCR" in out["text"] or "12345" in out["text"]
