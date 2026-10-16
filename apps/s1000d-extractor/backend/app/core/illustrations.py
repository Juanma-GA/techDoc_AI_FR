"""Extraction des figures et pictogrammes hors tableaux d'un PDF.

Les images associees a une legende de figure recoivent un nom derive de cette
legende (`figure-3-....jpg`) et un ICN dans l'IR. Les autres images sont rangees
a part comme pictogrammes (`picto_chapitre_....jpg`).

PDF uniquement (via PyMuPDF). DOCX / OCR : no-op gracieux (aucune image extraite,
les figures gardent leur placeholder ICN).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.ir import IRNode
from app.core.pdf_overlays import large_red_cross_rects

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_CHAPTER_NUMBER_RE = re.compile(r"^\s*(\d+(?:\s*[._-]\s*\d+)*)\b")
_PICTOGRAM_MAX_PIXELS = 65
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
_JPEG_QUALITY = 100

log = logging.getLogger("s1000d_extractor.illustrations")


class _PageAnalysis:
    def __init__(self, page: Any) -> None:
        self.page = page
        self._text_blocks: list | None = None
        self._dict_blocks: list | None = None
        self._drawings: list | None = None
        self.text_blocks_ms = 0.0
        self.dict_blocks_ms = 0.0
        self.drawings_ms = 0.0

    def text_blocks(self) -> list:
        if self._text_blocks is None:
            started = perf_counter()
            self._text_blocks = self.page.get_text("blocks")
            self.text_blocks_ms += (perf_counter() - started) * 1000
        return self._text_blocks

    def dict_blocks(self) -> list:
        if self._dict_blocks is None:
            import pymupdf as fitz

            started = perf_counter()
            flags = fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
            self._dict_blocks = self.page.get_text("dict", flags=flags).get("blocks", [])
            self.dict_blocks_ms += (perf_counter() - started) * 1000
        return self._dict_blocks

    def drawings(self) -> list:
        if self._drawings is None:
            started = perf_counter()
            self._drawings = self.page.get_drawings()
            self.drawings_ms += (perf_counter() - started) * 1000
        return self._drawings


def slugify(text: str, *, maxlen: int = 60) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug[:maxlen].strip("-") or "illustration"


def _save_pixmap(doc, xref: int, dest: Path) -> bool:
    """Enregistre l'image `xref` en JPG. Convertit CMYK/alpha en RGB. Best-effort."""
    import pymupdf as fitz

    try:
        extracted = doc.extract_image(xref)
        if (
            extracted
            and extracted.get("ext", "").lower() in {"jpg", "jpeg"}
            and not extracted.get("smask")
        ):
            # JPEG has no alpha channel; copy its encoded bytes without rasterizing.
            dest.write_bytes(extracted["image"])
            return True
        pix = fitz.Pixmap(doc, xref)
        if pix.n >= 5 or pix.alpha:            # CMYK ou canal alpha -> RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)

        pix.save(str(dest), jpg_quality=_JPEG_QUALITY)
        return True
    except Exception:
        return False



def _image_digest(doc, xref: int) -> str | None:
    """Return a digest of the embedded bytes without decoding image pixels."""
    try:

        image = doc.extract_image(xref).get("image")
        return hashlib.sha256(image).hexdigest() if image else None
    except Exception:
        return None



def _normalize_text(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _caption_rect(
    page, caption: str, page_analysis: _PageAnalysis | None = None
):

    import pymupdf as fitz

    wanted = _normalize_text(caption)
    blocks = page_analysis.text_blocks() if page_analysis else page.get_text("blocks")
    for block in blocks:
        if len(block) < 5 or _normalize_text(str(block[4])) != wanted:
            continue
        return fitz.Rect(block[:4])
    matches = page.search_for(caption)
    return matches[0] if matches else None


def _figure_caption_rect(
    page, caption: str, page_analysis: _PageAnalysis | None = None
):
    """Return the rectangle of this caption, not a merged text block."""
    matches = page.search_for(caption)
    if matches:
        return matches[0]
    return _caption_rect(page, caption, page_analysis)


def _table_bboxes(
    page: Any,
    page_number: int,
) -> list[tuple[float, float, float, float]]:
    try:
        tables = getattr(page.find_tables(), "tables", []) or []
    except Exception as exc:
        log.warning(
            "illustration_table_detection_failed page=%d error_type=%s",
            page_number,
            type(exc).__name__,
        )
        return []
    bboxes = []
    for table in tables:
        x0, y0, x1, y1 = table.bbox
        bboxes.append((float(x0), float(y0), float(x1), float(y1)))
    return bboxes


def _rect_center_in_table(
    rect: Any | None,
    table_bboxes: Sequence[tuple[float, float, float, float]],
) -> bool:
    if rect is None:
        return False
    center_x = (rect.x0 + rect.x1) / 2
    center_y = (rect.y0 + rect.y1) / 2
    return any(
        x0 <= center_x <= x1 and y0 <= center_y <= y1
        for x0, y0, x1, y1 in table_bboxes
    )


def _image_records(
    page,
    xref_digest_cache: dict[int, bytes] | None = None,
    table_bboxes: Sequence[tuple[float, float, float, float]] = (),
):
    """Return unique page image resources with their displayed rectangles."""
    import pymupdf as fitz

    records = []
    seen: set[int] = set()
    try:
        infos = page.get_image_info(hashes=True)
        image_refs = page.get_images()
    except Exception:
        infos = []
        image_refs = []
    table_only = bool(table_bboxes) and bool(infos) and all(
        _rect_center_in_table(fitz.Rect(image["bbox"]), table_bboxes)
        for image in infos
    )
    if infos:
        xrefs_by_digest: dict[bytes, int] = {}
        lookup_failed = False
        for image in image_refs:
            xref = int(image[0])
            if not xref:
                continue
            digest = xref_digest_cache.get(xref) if xref_digest_cache is not None else None
            if digest is None:
                try:
                    pixmap = fitz.Pixmap(page.parent, xref)
                    digest = pixmap.digest
                    del pixmap
                except Exception:
                    lookup_failed = True
                    break
                if xref_digest_cache is not None:
                    xref_digest_cache[xref] = digest
            xrefs_by_digest[digest] = xref
        if not lookup_failed:
            for info in infos:
                image_rect = fitz.Rect(info["bbox"])
                if _rect_center_in_table(image_rect, table_bboxes):
                    continue
                xref = xrefs_by_digest.get(info.get("digest"), 0)
                if not xref or xref in seen:
                    continue
                seen.add(xref)
                records.append((
                    xref,
                    image_rect,
                    int(info.get("width", 0)),
                    int(info.get("height", 0)),
                ))
    if records or table_only:
        return records
    return [
        (int(img[0]), None, int(img[2]), int(img[3]))
        for img in page.get_images(full=True)
    ]


def _is_pictogram(width: int, height: int) -> bool:
    return 0 < width <= _PICTOGRAM_MAX_PIXELS and 0 < height <= _PICTOGRAM_MAX_PIXELS


def _text_dict_blocks(
    page,
    page_analysis: _PageAnalysis | None = None,
) -> list[dict]:
    if page_analysis is not None:
        return page_analysis.dict_blocks()
    import pymupdf as fitz

    flags = fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
    return page.get_text("dict", flags=flags).get("blocks", [])


def _chapter_key(dm_section: IRNode | None, page_number: int) -> str:
    if dm_section is not None:
        match = _CHAPTER_NUMBER_RE.match(dm_section.text or "")
        if match:
            return re.sub(r"\s*[._-]\s*", "_", match.group(1))
    return f"p{page_number}"


def _dm_sections(root: IRNode, dm_level: int | None) -> list[IRNode]:
    """Retourne les sections racines des DM au niveau de decoupage choisi."""
    if dm_level is None:
        return [n for n in root.walk() if n.kind == "section" and n is not root]

    sections: list[IRNode] = []

    def collect(node: IRNode) -> None:
        for child in node.children:
            if child.kind != "section":
                continue
            if child.level is not None and child.level >= dm_level:
                sections.append(child)
            else:
                collect(child)

    collect(root)
    return sections


def _dm_for_page(dm_sections: list[IRNode], page_number: int) -> IRNode | None:
    candidates = [section for section in dm_sections if section.page is not None and section.page <= page_number]
    return candidates[-1] if candidates else None


def _match_figure(image_rect, figures, page_width: float, page_height: float):
    if image_rect is None:
        return None
    candidates = []
    image_center_x = (image_rect.x0 + image_rect.x1) / 2
    for figure, caption_rect in figures:
        # Some PDFs let the caption bbox overlap the image bbox by a few
        # points. Keep that nearest caption instead of assigning the image to
        # the following figure.
        if caption_rect is None or caption_rect.y0 < image_rect.y1 - 12:
            continue
        caption_center_x = (caption_rect.x0 + caption_rect.x1) / 2
        vertical_gap = max(0.0, caption_rect.y0 - image_rect.y1)
        score = (
            abs(image_center_x - caption_center_x) / page_width
            + vertical_gap / page_height
        )
        candidates.append((score, figure))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _set_figure_icn(figure: IRNode, name: str) -> None:
    if name not in figure.icns:
        figure.icns.append(name)
    if figure.icn is None:
        figure.icn = name


def _attach_pictogram(
    root: IRNode,
    dm_section: IRNode | None,
    page_number: int,
    xref: int,
    chapter: str,
    name: str,
    figure: IRNode | None = None,
) -> None:
    if figure is not None and not figure.icn:
        figure.text = f"Picto chapitre {chapter}"
        figure.icn = name
        figure.icns = [name]
        figure.is_pictogram = True
        return
    pictogram = IRNode(
        id=f"picto-{page_number}-{xref}",
        kind="figure",
        form="caption",
        text=f"Picto chapitre {chapter}",
        page=page_number,
        icn=name,
        icns=[name],
        is_pictogram=True,
    )
    (dm_section or root).children.append(pictogram)


def _vector_rects(
    page,
    caption_rect,
    page_analysis: _PageAnalysis | None = None,
    table_bboxes: Sequence[tuple[float, float, float, float]] = (),
):
    import pymupdf as fitz

    blocks = page_analysis.text_blocks() if page_analysis else page.get_text("blocks")
    text_rects = [
        fitz.Rect(block[:4])
        for block in blocks
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
    drawings = page_analysis.drawings() if page_analysis else page.get_drawings()
    for drawing in drawings:
        rect = fitz.Rect(drawing.get("rect", ()))
        if (
            rect.is_empty
            or _rect_center_in_table(rect, table_bboxes)
            or rect.y0 < previous_bottom
            or rect.y1 > caption_rect.y0
        ):
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


def _save_vector_figure(
    page,
    caption: str,
    dest: Path,
    page_analysis: _PageAnalysis | None = None,
    table_bboxes: Sequence[tuple[float, float, float, float]] = (),
) -> bool:
    import pymupdf as fitz

    caption_rect = _caption_rect(page, caption, page_analysis)
    if caption_rect is None or _rect_center_in_table(caption_rect, table_bboxes):
        return False
    rects = _vector_rects(page, caption_rect, page_analysis, table_bboxes)
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
        pixmap.save(str(dest), jpg_quality=_JPEG_QUALITY)
        return True
    except Exception:
        return False


def _is_composite_overlay_text(text: str) -> bool:
    text = _normalize_text(text)
    return bool(
        text
        and len(text) <= 120
        and not re.match(r"^(?:figure|fig\.?|illustration|tableau)\b", text, re.IGNORECASE)
    )


def _composite_bounds(
    page,
    image_rects,
    page_analysis: _PageAnalysis | None = None,
):
    import pymupdf as fitz

    image_bounds = image_rects[0]
    for rect in image_rects[1:]:
        image_bounds |= rect
    nearby = image_bounds + fitz.Rect(-20, -12, 20, 12)
    bounds = fitz.Rect(image_bounds)
    text_blocks = page_analysis.text_blocks() if page_analysis else page.get_text("blocks")
    dict_blocks = _text_dict_blocks(page, page_analysis)
    drawings = page_analysis.drawings() if page_analysis else page.get_drawings()

    for block in text_blocks:
        if len(block) < 5 or _is_composite_overlay_text(str(block[4])):
            continue
        rect = fitz.Rect(block[:4])
        if rect.y0 < image_bounds.y0 < rect.y1 and rect.y1 - image_bounds.y0 <= 12:
            bounds.y0 = max(bounds.y0, rect.y1 + 1)
        if rect.y0 < image_bounds.y1 < rect.y1 and image_bounds.y1 - rect.y0 <= 12:
            bounds.y1 = min(bounds.y1, rect.y0 - 1)

    for drawing in drawings:
        rect = fitz.Rect(drawing.get("rect", ()))
        if not rect.is_empty and rect.intersects(nearby):
            bounds |= rect

    for block in text_blocks:
        if len(block) < 5:
            continue
        text = _normalize_text(str(block[4]))
        if not _is_composite_overlay_text(text):
            continue
        rect = fitz.Rect(block[:4])
        if rect.intersects(nearby):
            bounds |= rect

    for rect in large_red_cross_rects(dict_blocks, image_rects):
        bounds |= rect

    return bounds


def _subtract_rect(rect, keep_rects):
    import pymupdf as fitz

    pieces = [rect]
    for keep in keep_rects:
        next_pieces = []
        for piece in pieces:
            overlap = piece & keep
            if overlap.is_empty:
                next_pieces.append(piece)
                continue
            if piece.y0 < overlap.y0:
                next_pieces.append(fitz.Rect(piece.x0, piece.y0, piece.x1, overlap.y0))
            if overlap.y1 < piece.y1:
                next_pieces.append(fitz.Rect(piece.x0, overlap.y1, piece.x1, piece.y1))
            if piece.x0 < overlap.x0:
                next_pieces.append(fitz.Rect(piece.x0, overlap.y0, overlap.x0, overlap.y1))
            if overlap.x1 < piece.x1:
                next_pieces.append(fitz.Rect(overlap.x1, overlap.y0, piece.x1, overlap.y1))
        pieces = next_pieces
    return [piece for piece in pieces if not piece.is_empty]


def _save_composite_figure(
    page,
    image_rects,
    dest: Path,
    page_analysis: _PageAnalysis | None = None,
) -> bool:
    """Rasterise une figure composee et ses annotations vectorielles."""
    import pymupdf as fitz

    if not image_rects:
        return False
    bounds = _composite_bounds(page, image_rects, page_analysis)
    cross_rects = large_red_cross_rects(_text_dict_blocks(page, page_analysis), image_rects)
    bounds &= page.rect
    if bounds.width < 10 or bounds.height < 10:
        return False
    try:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=bounds, alpha=False)
        text_blocks = page_analysis.text_blocks() if page_analysis else page.get_text("blocks")
        for block in text_blocks:
            if len(block) < 5 or _is_composite_overlay_text(str(block[4])):
                continue
            text_rect = fitz.Rect(block[:4]) & bounds
            if text_rect.is_empty:
                continue
            for piece in _subtract_rect(text_rect, [*image_rects, *cross_rects]):
                pixmap.set_rect(
                    fitz.IRect(
                        round((piece.x0 - bounds.x0) * 2),
                        round((piece.y0 - bounds.y0) * 2),
                        round((piece.x1 - bounds.x0) * 2),
                        round((piece.y1 - bounds.y0) * 2),
                    ),
                    (255, 255, 255),
                )
        pixmap.save(str(dest), jpg_quality=_JPEG_QUALITY)
        return True
    except Exception:
        return False


def _has_figure_overlays(
    page,
    image_rects,
    page_analysis: _PageAnalysis | None = None,
) -> bool:
    import pymupdf as fitz

    if not image_rects:
        return False
    bounds = image_rects[0]
    for rect in image_rects[1:]:
        bounds |= rect
    nearby = bounds + fitz.Rect(-20, -12, 20, 12)
    if large_red_cross_rects(_text_dict_blocks(page, page_analysis), image_rects):
        return True
    text_blocks = page_analysis.text_blocks() if page_analysis else page.get_text("blocks")
    if any(
        len(block) >= 5
        and _is_composite_overlay_text(str(block[4]))
        and fitz.Rect(block[:4]).intersects(nearby)
        for block in text_blocks
    ):
        return True
    drawings = page_analysis.drawings() if page_analysis else page.get_drawings()
    return any(
        not (rect := fitz.Rect(drawing.get("rect", ()))).is_empty
        and rect.intersects(nearby)
        for drawing in drawings
    )


def attach_illustrations(
    root: IRNode,
    *,
    pdf_path: str,
    out_dir: Path,
    doc_id: str,
    dm_level: int | None = None,
) -> int:
    """Extrait les figures hors tableaux et range les images non associees comme pictogrammes.

    Les figures contenant plusieurs bitmaps sont rasterisees en une seule image
    afin de conserver aussi les annotations vectorielles superposees. Renvoie le
    nombre de fichiers enregistres. No-op si PyMuPDF echoue ou s'il n'y a pas d'image.
    """
    try:
        import pymupdf as fitz
    except Exception:
        return 0
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return 0

    started = perf_counter()
    timings = {
        "caption_lookup_ms": 0.0,
        "image_info_ms": 0.0,
        "image_digest_ms": 0.0,
        "image_processing_ms": 0.0,
        "text_blocks_ms": 0.0,
        "dict_blocks_ms": 0.0,
        "drawings_ms": 0.0,
    }
    image_occurrence_count = 0
    unique_xref_count = 0
    composite_count = 0
    vector_count = 0

    # Figures de l'IR par page (dans l'ordre), pour le nommage.
    figs_by_page: dict[int, list[IRNode]] = {}
    pictogram_callouts_by_page: dict[int, list[IRNode]] = {}
    dm_sections = _dm_sections(root, dm_level)
    for n in root.walk():
        if n.kind == "figure" and n.page is not None:
            figs_by_page.setdefault(n.page, []).append(n)
        if n.kind == "admonition" and n.is_pictogram and n.page is not None:
            pictogram_callouts_by_page.setdefault(n.page, []).append(n)

    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    # `seen` est GLOBAL au document : une meme image (xref) reutilisee sur
    # plusieurs pages (logo, bandeau, figure repetee) ne doit etre extraite
    # qu'UNE fois, sinon le dossier se remplit de doublons.
    seen: set[int] = set()
    seen_digests: set[str] = set()
    xref_digest_cache: dict[int, bytes] = {}
    try:
        for pidx, page in enumerate(doc, start=1):
            page_analysis = _PageAnalysis(page)
            table_bboxes = _table_bboxes(page, pidx)
            figs = list(figs_by_page.get(pidx, []))
            stage_started = perf_counter()
            figure_anchors = [
                (figure, _figure_caption_rect(page, figure.text, page_analysis))
                for figure in figs
            ]
            figures_in_tables = {
                id(figure)
                for figure, caption_rect in figure_anchors
                if _rect_center_in_table(caption_rect, table_bboxes)
            }
            figure_anchors = [
                (figure, caption_rect)
                for figure, caption_rect in figure_anchors
                if id(figure) not in figures_in_tables
            ]
            timings["caption_lookup_ms"] += (perf_counter() - stage_started) * 1000
            stage_started = perf_counter()
            image_records = _image_records(page, xref_digest_cache, table_bboxes)
            timings["image_info_ms"] += (perf_counter() - stage_started) * 1000
            image_occurrence_count += len(image_records)
            standard_matches = {
                id(figure)
                for xref, image_rect, width, height in image_records
                if image_rect is not None
                and not _is_pictogram(width, height)
                for figure in [_match_figure(
                    image_rect,
                    figure_anchors,
                    float(page.rect.width),
                    float(page.rect.height),
                )]
                if figure is not None
            }
            composite_records: dict[int, tuple[IRNode, list[tuple[int, object]]]] = {}
            page_processing_started = perf_counter()
            for xref, image_rect, width, height in image_records:
                if xref in seen:
                    continue
                seen.add(xref)
                unique_xref_count += 1
                stage_started = perf_counter()
                digest = _image_digest(doc, xref)
                timings["image_digest_ms"] += (perf_counter() - stage_started) * 1000
                if digest is not None and digest in seen_digests:
                    continue
                if digest is not None:
                    seen_digests.add(digest)
                if _is_pictogram(width, height):
                    figure = _match_figure(
                        image_rect,
                        figure_anchors,
                        float(page.rect.width),
                        float(page.rect.height),
                    )
                    if figure is not None and id(figure) in standard_matches:
                        continue
                    dm_section = _dm_for_page(dm_sections, pidx)
                    chapter = _chapter_key(dm_section, pidx)
                    name = _unique_name(out_dir, f"picto_chapitre_{chapter}")
                    if _save_pixmap(doc, xref, out_dir / name):
                        saved += 1
                        if pictogram_callouts_by_page.get(pidx):
                            continue
                        _attach_pictogram(root, dm_section, pidx, xref, chapter, name, figure)
                    continue
                fig = _match_figure(
                    image_rect,
                    figure_anchors,
                    float(page.rect.width),
                    float(page.rect.height),
                )
                if fig is not None and image_rect is not None:
                    record = composite_records.setdefault(id(fig), (fig, []))
                    record[1].append((xref, image_rect))
                    continue
                dm_section = _dm_for_page(dm_sections, pidx)
                chapter = _chapter_key(dm_section, pidx)
                name = _unique_name(out_dir, f"picto_chapitre_{chapter}")
                if _save_pixmap(doc, xref, out_dir / name):
                    saved += 1
                    if not pictogram_callouts_by_page.get(pidx):
                        _attach_pictogram(root, dm_section, pidx, xref, chapter, name)
            for fig, records in composite_records.values():
                base = slugify(fig.text) if fig.text else f"illustration-{doc_id[:8]}-p{pidx}"
                name = _unique_name(out_dir, base)
                image_rects = [image_rect for _, image_rect in records]
                composite = len(records) > 1 or _has_figure_overlays(
                    page, image_rects, page_analysis
                )
                if composite:
                    composite_count += 1
                    success = _save_composite_figure(
                        page, image_rects, out_dir / name, page_analysis
                    )
                else:
                    success = _save_pixmap(doc, records[0][0], out_dir / name)
                if success:
                    saved += 1
                    _set_figure_icn(fig, name)
                elif composite:
                    for xref, _ in records:
                        fallback_name = _unique_name(out_dir, base)
                        if _save_pixmap(doc, xref, out_dir / fallback_name):
                            saved += 1
                            _set_figure_icn(fig, fallback_name)
            for fig in figs:
                if fig.icn or id(fig) in figures_in_tables:
                    continue
                vector_count += 1
                base = slugify(fig.text) if fig.text else f"illustration-{doc_id[:8]}-p{pidx}"
                name = _unique_name(out_dir, base)
                if _save_vector_figure(
                    page,
                    fig.text,
                    out_dir / name,
                    page_analysis,
                    table_bboxes,
                ):
                    saved += 1
                    _set_figure_icn(fig, name)
            timings["image_processing_ms"] += (perf_counter() - page_processing_started) * 1000
            timings["text_blocks_ms"] += page_analysis.text_blocks_ms
            timings["dict_blocks_ms"] += page_analysis.dict_blocks_ms
            timings["drawings_ms"] += page_analysis.drawings_ms
        log.info(
            "illustration_breakdown duration_ms=%.1f page_count=%d figure_count=%d "
            "image_occurrence_count=%d unique_xref_count=%d saved_count=%d "
            "composite_count=%d vector_count=%d caption_lookup_ms=%.1f image_info_ms=%.1f "
            "image_digest_ms=%.1f image_processing_ms=%.1f text_blocks_ms=%.1f "
            "dict_blocks_ms=%.1f drawings_ms=%.1f",
            (perf_counter() - started) * 1000,
            doc.page_count,
            sum(len(figures) for figures in figs_by_page.values()),
            image_occurrence_count,
            unique_xref_count,
            saved,
            composite_count,
            vector_count,
            timings["caption_lookup_ms"],
            timings["image_info_ms"],
            timings["image_digest_ms"],
            timings["image_processing_ms"],
            timings["text_blocks_ms"],
            timings["dict_blocks_ms"],
            timings["drawings_ms"],
        )
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
            import pymupdf as fitz

            pixmap = fitz.Pixmap(str(source))
            if pixmap.n >= 5 or pixmap.alpha:
                pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
            if target.suffix.lower() == ".png":
                pixmap.save(str(destination))
            else:
                pixmap.save(str(destination), jpg_quality=_JPEG_QUALITY)
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
