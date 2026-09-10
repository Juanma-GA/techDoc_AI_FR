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

import hashlib
import os
import re
from pathlib import Path

from app.core.ir import IRNode

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


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


def _image_digest(doc, xref: int) -> str | None:
    """Return a stable digest of the decoded image pixels."""
    import fitz

    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n >= 5 or pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        return hashlib.sha256(pix.samples).hexdigest()
    except Exception:
        return None


def _normalize_text(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _caption_rect(page, caption: str):
    import fitz

    wanted = _normalize_text(caption)
    for block in page.get_text("blocks"):
        if len(block) < 5 or _normalize_text(str(block[4])) != wanted:
            continue
        return fitz.Rect(block[:4])
    matches = page.search_for(caption)
    return matches[0] if matches else None


def _vector_rects(page, caption_rect):
    import fitz

    text_rects = [
        fitz.Rect(block[:4])
        for block in page.get_text("blocks")
        if len(block) >= 5 and str(block[4]).strip()
    ]
    previous_bottom = max(
        (
            rect.y1
            for rect in text_rects
            if rect.y1 <= caption_rect.y0 + 1
            and not (
                rect.x0 >= page.rect.width * 0.85
                and rect.width <= page.rect.width * 0.12
            )
        ),
        default=0.0,
    )
    has_edge_rail = any(
        rect.y1 <= caption_rect.y0 + 1
        and rect.x0 >= page.rect.width * 0.85
        and rect.width <= page.rect.width * 0.12
        for rect in text_rects
    )
    rects = []
    for drawing in page.get_drawings():
        rect = fitz.Rect(drawing.get("rect", ()))
        if rect.is_empty or rect.y0 < previous_bottom or rect.y1 > caption_rect.y0:
            continue
        rects.append(rect)
    if not rects:
        return []

    intervals = sorted((rect.x0, rect.x1) for rect in rects)
    merged: list[list[float]] = []
    for x0, x1 in intervals:
        if not merged or x0 > merged[-1][1] + 12:
            merged.append([x0, x1])
        else:
            merged[-1][1] = max(merged[-1][1], x1)
    edge_limit = float(page.rect.width) - 8
    min_edge_width = float(page.rect.width) * 0.12
    main_intervals = [
        interval
        for interval in merged
        if not (
            has_edge_rail
            and interval[1] >= edge_limit
            and interval[1] - interval[0] < min_edge_width
        )
    ]
    if not main_intervals:
        main_intervals = [max(merged, key=lambda interval: interval[1] - interval[0])]
    return [
        rect
        for rect in rects
        if any(rect.x1 >= x0 and rect.x0 <= x1 for x0, x1 in main_intervals)
    ]


def _save_vector_figure(page, caption: str, dest: Path) -> bool:
    import fitz

    caption_rect = _caption_rect(page, caption)
    if caption_rect is None:
        return False
    rects = _vector_rects(page, caption_rect)
    if not rects:
        return False
    bounds = rects[0]
    for rect in rects[1:]:
        bounds |= rect
    bounds = bounds + fitz.Rect(-4, -4, 4, 4)
    bounds &= page.rect
    if bounds.width < 10 or bounds.height < 10:
        return False
    try:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=bounds, alpha=False)
        pixmap.save(str(dest), jpg_quality=85)
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
    # `seen` est GLOBAL au document : une meme image (xref) reutilisee sur
    # plusieurs pages (logo, bandeau, figure repetee) ne doit etre extraite
    # qu'UNE fois, sinon le dossier se remplit de doublons.
    seen: set[int] = set()
    seen_digests: set[str] = set()
    try:
        for pidx, page in enumerate(doc, start=1):
            figs = list(figs_by_page.get(pidx, []))
            for img in page.get_images(full=True):
                xref = int(img[0])
                if xref in seen:
                    continue
                seen.add(xref)
                digest = _image_digest(doc, xref)
                if digest is not None and digest in seen_digests:
                    continue
                if digest is not None:
                    seen_digests.add(digest)
                fig = figs.pop(0) if figs else None
                base = slugify(fig.text) if fig and fig.text else f"illustration-{doc_id[:8]}-p{pidx}-{xref}"
                name = _unique_name(out_dir, base)
                if _save_pixmap(doc, xref, out_dir / name):
                    saved += 1
                    if fig is not None:
                        fig.icn = name
            for fig in figs:
                base = slugify(fig.text) if fig.text else f"illustration-{doc_id[:8]}-p{pidx}"
                name = _unique_name(out_dir, base)
                if _save_vector_figure(page, fig.text, out_dir / name):
                    saved += 1
                    fig.icn = name
        return saved
    finally:
        doc.close()


def rename_illustration(out_dir: Path, current_name: str, target_name: str) -> str | None:
    """Renomme une image extraite, avec conversion si l'extension change."""
    current = Path(current_name)
    target = Path(target_name)
    if current.name != current_name or target.name != target_name:
        return None
    if current.suffix.lower() not in _IMAGE_SUFFIXES or target.suffix.lower() not in _IMAGE_SUFFIXES:
        return None

    source = out_dir / current_name
    if not source.exists():
        return None
    if _same_path(source, out_dir / target_name):
        return source.name

    final_name = _unique_filename(out_dir, target_name, exclude=source)
    destination = out_dir / final_name
    try:
        if current.suffix.lower() == target.suffix.lower():
            source.replace(destination)
        else:
            import fitz

            pixmap = fitz.Pixmap(str(source))
            if pixmap.n >= 5 or pixmap.alpha:
                pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
            if target.suffix.lower() == ".png":
                pixmap.save(str(destination))
            else:
                pixmap.save(str(destination), jpg_quality=85)
            source.unlink()
    except Exception:
        destination.unlink(missing_ok=True)
        return None
    return final_name


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(os.path.abspath(str(right)))


def _unique_filename(out_dir: Path, filename: str, *, exclude: Path | None = None) -> str:
    path = Path(filename)
    name = filename
    n = 2
    while (out_dir / name).exists() and not (exclude and _same_path(out_dir / name, exclude)):
        name = f"{path.stem}-{n}{path.suffix}"
        n += 1
    return name


def _unique_name(out_dir: Path, base: str) -> str:
    """Nom de fichier libre : deux legendes identiques ne doivent pas s'ecraser."""
    return _unique_filename(out_dir, f"{base}.jpg")
