"""Extraction des illustrations d'un PDF -> fichiers JPG nommes.

On enregistre TOUTES les images du PDF (l'utilisateur veut pouvoir les
recuperer), en les nommant d'apres la legende voisine ("Figure 3 ..." ->
`figure-3-....jpg`) quand elle existe, sinon `illustration_<doc>_<n>.jpg`. Chaque
figure de l'IR recoit alors son ICN (nom de fichier) que le serialiseur
reference dans `<graphic infoEntityIdent=...>` au lieu du placeholder TODO.

PDF uniquement (via PyMuPDF). DOCX / OCR : no-op gracieux (aucune image extraite,
les figures gardent leur placeholder ICN).
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.ir import IRNode

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, *, maxlen: int = 60) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug[:maxlen].strip("-") or "illustration"


def _save_pixmap(doc, xref: int, dest: Path) -> bool:
    """Enregistre l'image `xref` en JPG. Convertit CMYK/alpha en RGB. Best-effort."""
    import fitz

    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n >= 5 or pix.alpha:            # CMYK ou canal alpha -> RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(str(dest), jpg_quality=85)
        return True
    except Exception:
        return False


def attach_illustrations(root: IRNode, *, pdf_path: str, out_dir: Path, doc_id: str) -> int:
    """Extrait les images du PDF, les enregistre en JPG et pose l'ICN sur les
    figures de l'IR (appariement par page + ordre de lecture). Renvoie le nombre
    d'images enregistrees. No-op si PyMuPDF echoue ou s'il n'y a pas d'image."""
    try:
        import fitz
    except Exception:
        return 0
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return 0

    # Figures de l'IR par page (dans l'ordre), pour le nommage.
    figs_by_page: dict[int, list[IRNode]] = {}
    for n in root.walk():
        if n.kind == "figure" and n.page is not None:
            figs_by_page.setdefault(n.page, []).append(n)

    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    try:
        for pidx, page in enumerate(doc, start=1):
            seen: set[int] = set()
            figs = list(figs_by_page.get(pidx, []))
            for img in page.get_images(full=True):
                xref = int(img[0])
                if xref in seen:
                    continue
                seen.add(xref)
                fig = figs.pop(0) if figs else None
                base = slugify(fig.text) if fig and fig.text else f"illustration-{doc_id[:8]}-p{pidx}-{xref}"
                name = f"{base}.jpg"
                if _save_pixmap(doc, xref, out_dir / name):
                    saved += 1
                    if fig is not None:
                        fig.icn = name
        return saved
    finally:
        doc.close()
