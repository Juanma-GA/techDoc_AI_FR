"""Rendu PDF fidele du document pour la vue de revue.

Chaine : `.docx` (version courante) --LibreOffice--> PDF (mise en page reelle),
puis PyMuPDF pour (a) rasteriser chaque page en PNG et (b) localiser le texte de
chaque anomalie (`search_for`) -> bbox normalisees en % (surlignage cote front).

Le PDF est **cache par version** dans `<doc_dir>/v<N>.pdf` (conversion lente :
~5 s a chaud, plus au 1er lancement de LibreOffice). Les bbox sont recalculees a
la demande (rapide une fois le PDF present).
"""

from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

from app.core import docx_versioning as ver
from app.core.doc_convert import convert_to_pdf

log = logging.getLogger("word_reviewer.pdf_render")

# Longueur max d'un texte recherche : au-dela, search_for echoue (retours ligne).
_MAX_NEEDLE = 80


def pdf_path_for(storage_dir: str, version: int) -> Path:
    return ver.doc_dir(storage_dir) / f"v{version}.pdf"


def original_doc_path(storage_dir: str) -> Path:
    """`.doc` d'origine conserve a l'upload (rendu PDF fidele Word, une seule conversion)."""
    return ver.doc_dir(storage_dir) / "original.doc"


def _pdf_source(storage_dir: str, version: int) -> Path | None:
    """Source la plus fidele pour le PDF de cette version.

    v0 non editee : le `.doc` d'origine s'il existe (rendu Word direct, sans passer
    par le .docx converti). Versions editees : le `.docx` de la version.
    """
    if version == 0:
        orig = original_doc_path(storage_dir)
        if orig.exists() and orig.stat().st_size > 0:
            return orig
    docx = ver.version_path(storage_dir, version)
    return docx if docx.exists() else None


def ensure_pdf(storage_dir: str, version: int) -> Path | None:
    """PDF fidele de la version, genere + cache a la demande. None si aucun
    convertisseur (Word/LibreOffice) disponible."""
    out = pdf_path_for(storage_dir, version)
    if out.exists() and out.stat().st_size > 0:
        return out
    src = _pdf_source(storage_dir, version)
    if src is None:
        return None
    produced = convert_to_pdf(src, ver.doc_dir(storage_dir))  # ecrit <stem>.pdf
    if produced is None or not produced.exists():
        return None
    if produced != out:
        try:
            produced.replace(out)
        except OSError:
            return produced
    return out


def page_count(pdf: Path) -> int:
    doc = fitz.open(str(pdf))
    try:
        return doc.page_count
    finally:
        doc.close()


def render_page_png(pdf: Path, page_number: int, dpi: int = 120) -> bytes:
    doc = fitz.open(str(pdf))
    try:
        page = doc.load_page(page_number - 1)
        return page.get_pixmap(dpi=dpi, alpha=False).tobytes("png")
    finally:
        doc.close()


def _clean_needle(text: str) -> str:
    # Une seule ligne, espaces normalises, tronque : maximise les matchs search_for.
    return " ".join((text or "").split())[:_MAX_NEEDLE].strip()


def compute_highlights(pdf: Path, needles: list[tuple[str, str]]) -> dict:
    """`needles` = [(suggestion_id, texte_a_chercher)].

    Retourne {page_count, highlights:[{id, page, boxes:[{left,top,width,height}]}]}
    ou les boxes sont en **pourcentage** de la page (origine haut-gauche).
    """
    doc = fitz.open(str(pdf))
    try:
        pages_text = [doc.load_page(i).get_text("text").lower() for i in range(doc.page_count)]
        highlights: list[dict] = []
        for sid, raw in needles:
            needle = _clean_needle(raw)
            if len(needle) < 2:
                continue
            low = needle.lower()
            for i, ptext in enumerate(pages_text):
                if low not in ptext:
                    continue
                page = doc.load_page(i)
                rects = page.search_for(needle)
                if not rects:
                    continue
                w, h = page.rect.width or 1, page.rect.height or 1
                boxes = [
                    {
                        "left": round(100 * r.x0 / w, 3),
                        "top": round(100 * r.y0 / h, 3),
                        "width": round(100 * (r.x1 - r.x0) / w, 3),
                        "height": round(100 * (r.y1 - r.y0) / h, 3),
                    }
                    for r in rects
                ]
                highlights.append({"id": sid, "page": i + 1, "boxes": boxes})
                break  # 1re page contenant le texte
        return {"page_count": doc.page_count, "highlights": highlights}
    finally:
        doc.close()
