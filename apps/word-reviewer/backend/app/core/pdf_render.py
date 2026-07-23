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
    """`needles` = [(suggestion_id, texte_a_chercher)], **en ordre de lecture**.

    Retourne {page_count, highlights:[{id, page, boxes:[{left,top,width,height}]}]}
    ou les boxes sont en **pourcentage** de la page (origine haut-gauche).

    Chaque anomalie recoit AU PLUS une boite. Quand un meme texte apparait
    plusieurs fois (faute repetee, ou plusieurs anomalies sur le meme bloc via le
    repli « texte du bloc »), la k-ieme anomalie portant ce texte est associee a la
    k-ieme occurrence en ordre de lecture. Sans ca, `search_for` collait TOUTES les
    occurrences a chaque anomalie -> boites superposees, et le clic tombait sur la
    derniere rendue (mauvaise anomalie).
    """
    doc = fitz.open(str(pdf))
    try:
        page_count = doc.page_count
        # Occurrences (page, rect) d'un texte, en ordre de lecture, mises en cache.
        cache: dict[str, list[tuple[int, "fitz.Rect"]]] = {}

        def _occurrences(needle: str) -> list[tuple[int, "fitz.Rect"]]:
            key = needle.lower()
            if key not in cache:
                found: list[tuple[int, "fitz.Rect"]] = []
                for i in range(page_count):
                    for r in doc.load_page(i).search_for(needle):
                        found.append((i, r))
                found.sort(key=lambda pr: (pr[0], round(pr[1].y0, 1), round(pr[1].x0, 1)))
                cache[key] = found
            return cache[key]

        used: dict[str, int] = {}  # combien d'occurrences deja consommees par texte
        highlights: list[dict] = []
        for sid, raw in needles:
            needle = _clean_needle(raw)
            if len(needle) < 2:
                continue
            occ = _occurrences(needle)
            k = used.get(needle.lower(), 0)
            used[needle.lower()] = k + 1
            if k >= len(occ):
                continue  # occurrence deja prise -> pas de boite (mieux qu'une fausse)
            i, r = occ[k]
            page = doc.load_page(i)
            w, h = page.rect.width or 1, page.rect.height or 1
            highlights.append(
                {
                    "id": sid,
                    "page": i + 1,
                    "boxes": [
                        {
                            "left": round(100 * r.x0 / w, 3),
                            "top": round(100 * r.y0 / h, 3),
                            "width": round(100 * (r.x1 - r.x0) / w, 3),
                            "height": round(100 * (r.y1 - r.y0) / h, 3),
                        }
                    ],
                }
            )
        return {"page_count": page_count, "highlights": highlights}
    finally:
        doc.close()
