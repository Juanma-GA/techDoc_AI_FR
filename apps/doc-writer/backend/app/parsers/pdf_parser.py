"""Parseur PDF via PyMuPDF (fitz).

Strategie en cascade (chaque niveau ne se declenche que si le precedent echoue
ou rend du vide) :

0. **Couche texte native** : si le PDF a une couche texte exploitable (cas des
   PDF editables, ex. CV avec texte selectionnable) -> on l'utilise telle
   quelle. Fidele, instantane, gratuit : ni vision ni OCR.
1. **VISION (multimodal)** — quand la couche texte manque (PDF image / scan /
   CV graphique) et qu'un client Mistral est fourni : les pages sont rendues en
   images et interpretees par un modele vision. Lit AUSSI le graphique
   (drapeaux -> langue, barres/points/jauges -> niveau) que l'OCR texte ne
   comprend pas. Limite a `_VISION_MAX_PAGES` pages (au-dela -> niveau 2).
2. **OCR document** (/v1/ocr) — texte + structure (colonnes, tableaux).
3. **Extraction LOCALE** — couche texte PyMuPDF + OCR Tesseract sur les pages
   sans texte. Tesseract est un binaire systeme externe (cf. README) ; absent
   -> warning une fois, page scannee vide, pas de crash.
"""

from __future__ import annotations

import logging

import fitz  # type: ignore[import-untyped]

from app.config import settings

log = logging.getLogger("doc_writer.pdf_parser")

# Evite de spammer un warning par page quand Tesseract est absent : on ne
# previent qu'une fois par process.
_ocr_unavailable_warned = False

# Rendu des pages pour la vision : DPI modere (lisible sans alourdir l'upload)
# et plafond de pages (au-dela on bascule sur l'OCR document, plus adapte aux
# longs PDF qu'un envoi de N images).
_VISION_DPI = 150
_VISION_MAX_PAGES = 10


def _render_pages_png(path: str) -> list[bytes] | None:
    """Rend chaque page du PDF en PNG (pour la vision). Renvoie None si le
    document depasse `_VISION_MAX_PAGES` (on laissera l'OCR document gerer)."""
    images: list[bytes] = []
    zoom = _VISION_DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(path) as doc:
        if doc.page_count > _VISION_MAX_PAGES:
            return None
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))
    return images


def _parse_via_vision(path: str, mistral) -> str:  # type: ignore[no-untyped-def]
    """Transcription vision du PDF (pages -> images -> modele multimodal).
    Renvoie '' si indisponible / en erreur (l'appelant passe au repli OCR)."""
    try:
        images = _render_pages_png(path)
        if not images:
            return ""
        text = mistral.vision_extract(images)
        if text.strip():
            log.info("Vision Mistral appliquee sur %s (%d page(s))", path, len(images))
            return text
        return ""
    except Exception as e:  # noqa: BLE001
        log.warning(
            "Vision Mistral echoue (%s: %s) -> repli OCR/local.",
            type(e).__name__, e,
        )
        return ""


def _ocr_page(page) -> str:  # type: ignore[no-untyped-def]
    """Texte OCR d'une page (rendue en image a `pdf_ocr_dpi`). Renvoie '' si
    l'OCR echoue (Tesseract absent, langue manquante...) en loggant une fois."""
    global _ocr_unavailable_warned
    try:
        tp = page.get_textpage_ocr(
            flags=0,
            language=settings.pdf_ocr_lang,
            dpi=settings.pdf_ocr_dpi,
            full=True,
            tessdata=settings.pdf_ocr_tessdata or None,
        )
        return page.get_text("text", textpage=tp) or ""
    except Exception as e:  # noqa: BLE001
        if not _ocr_unavailable_warned:
            log.warning(
                "OCR PDF indisponible (Tesseract installe ? langue '%s' presente ? "
                "TESSDATA_PREFIX / pdf_ocr_tessdata defini ?) : %s. Les pages "
                "scannees resteront vides.",
                settings.pdf_ocr_lang,
                e,
            )
            _ocr_unavailable_warned = True
        return ""


def _parse_via_mistral(path: str, mistral) -> str:  # type: ignore[no-untyped-def]
    """OCR du PDF entier via l'API Mistral. Renvoie le texte, ou '' si l'appel
    echoue (l'appelant retombe alors sur l'extraction locale)."""
    try:
        with open(path, "rb") as f:
            pdf_bytes = f.read()
        text = mistral.ocr_pdf(pdf_bytes)
        if text.strip():
            log.info("OCR Mistral applique sur %s", path)
            return text
        return ""
    except Exception as e:  # noqa: BLE001
        log.warning(
            "OCR Mistral echoue (%s: %s) -> repli sur l'extraction locale.",
            type(e).__name__, e,
        )
        return ""


def _native_text(path: str) -> tuple[str, int, int]:
    """Couche texte native (sans OCR). Renvoie (texte, nb_pages, nb_pages_avec_texte)."""
    parts: list[str] = []
    n_pages = 0
    n_text_pages = 0
    with fitz.open(path) as doc:
        for page in doc:
            n_pages += 1
            text = page.get_text("text") or ""
            if text.strip():
                n_text_pages += 1
                parts.append(text)
    return "\n\n".join(parts), n_pages, n_text_pages


def _native_sufficient(text: str, n_pages: int, n_text_pages: int) -> bool:
    """Couche texte jugee exploitable : presente sur la majorite des pages ET
    assez dense (un PDF scanne / exporte en image donne ~0 caractere). Evite un
    appel vision/OCR inutile sur les PDF editables (cas le plus frequent)."""
    if n_pages == 0 or n_text_pages < (n_pages + 1) // 2:
        return False
    return len(text.strip()) >= 100 * n_pages


def _native_with_tesseract(path: str) -> str:
    """Extraction locale finale : couche texte + OCR Tesseract sur les pages
    sans texte (repli quand Mistral est indisponible)."""
    parts: list[str] = []
    ocr_pages = 0
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text("text") or ""
            if not text.strip() and settings.pdf_ocr_enabled:
                text = _ocr_page(page)
                if text.strip():
                    ocr_pages += 1
            if text.strip():
                parts.append(text)
    if ocr_pages:
        log.info("OCR Tesseract applique sur %d page(s) de %s", ocr_pages, path)
    return "\n\n".join(parts)


def parse(path: str, *, mistral=None) -> dict[str, str]:  # type: ignore[no-untyped-def]
    # 1. Couche texte native suffisante (PDF editable, ex. CV avec texte
    #    selectionnable) -> on l'utilise directement : fidele, instantane,
    #    gratuit. Pas d'appel vision/OCR.
    native, n_pages, n_text_pages = _native_text(path)
    if _native_sufficient(native, n_pages, n_text_pages):
        return {"text": native}

    # 2. Couche texte absente/pauvre (PDF image, scan, CV graphique) : Mistral
    #    vision (defaut, lit drapeaux/jauges) -> repli OCR document.
    if mistral is not None:
        text = _parse_via_vision(path, mistral)
        if text.strip():
            return {"text": text}
        text = _parse_via_mistral(path, mistral)
        if text.strip():
            return {"text": text}

    # 3. Repli local final : Tesseract sur les pages sans texte.
    return {"text": _native_with_tesseract(path)}
