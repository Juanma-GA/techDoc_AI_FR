"""Extraction des images/illustrations d'un PDF -> fichiers JPG sur disque.

Meme approche que le s1000d-extractor : PyMuPDF (`fitz`), on parcourt les pages,
on recupere chaque image (`page.get_images`) et on l'enregistre en JPG
(conversion CMYK/alpha -> RGB). Best-effort : si PyMuPDF echoue ou si le fichier
n'est pas un PDF, on renvoie une liste vide (fallback gracieux, jamais d'erreur).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _save_pixmap(doc, xref: int, dest: Path) -> bool:  # type: ignore[no-untyped-def]
    """Enregistre l'image `xref` en JPG. Convertit CMYK/alpha en RGB. Best-effort."""
    import fitz

    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n >= 5 or pix.alpha:  # CMYK ou canal alpha -> RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(str(dest), jpg_quality=85)
        return True
    except Exception:  # noqa: BLE001
        return False


def extract_images(pdf_bytes: bytes, out_dir: Path, doc_id: str) -> list[dict]:
    """Extrait toutes les images du PDF, les enregistre en JPG dans `out_dir` et
    renvoie `[{filename, page}]`. No-op (liste vide) si PyMuPDF manque, si le
    contenu n'est pas un PDF lisible, ou s'il n'y a aucune image."""
    try:
        import fitz
    except Exception:  # noqa: BLE001
        logger.warning("PyMuPDF indisponible - extraction images ignoree")
        return []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    try:
        for pidx, page in enumerate(doc, start=1):
            seen: set[int] = set()
            for img in page.get_images(full=True):
                xref = int(img[0])
                if xref in seen:
                    continue
                seen.add(xref)
                # Prefixe doc_id : unicite entre uploads successifs dans la meme table.
                name = f"{doc_id[:8]}_p{pidx}_{xref}.jpg"
                if _save_pixmap(doc, xref, out_dir / name):
                    results.append({"filename": name, "page": pidx})
        return results
    finally:
        doc.close()
