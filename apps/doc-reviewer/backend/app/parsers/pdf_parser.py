"""PDF parsing for the reviewer.

`parse_pdf(path)` returns a list of pages, each with its raw text and a
flat list of spans `{text, bbox, font, size}`. Span-level granularity is
required so suggestions can be located precisely (page + bbox).

Also flags PDFs that won't allow safe in-place edits:
- digitally signed (signature is invalidated by any patch).
- raster pages with no extractable text layer (no OCR in this POC).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class Span:
    text: str
    bbox: tuple[float, float, float, float]
    page: int  # 1-indexed
    font: str
    size: float


@dataclass
class ParsedPage:
    page: int  # 1-indexed
    text: str
    spans: list[Span] = field(default_factory=list)
    has_text_layer: bool = True
    page_type: str | None = None


@dataclass
class ParsedPdf:
    page_count: int
    pages: list[ParsedPage]
    full_text: str
    is_signed: bool


def parse_pdf(path: str | Path) -> ParsedPdf:
    doc = fitz.open(str(path))
    try:
        is_signed = _has_digital_signature(doc)
        pages: list[ParsedPage] = []
        all_text: list[str] = []

        for idx, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            data = page.get_text("dict")
            spans: list[Span] = []
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        s_text = span.get("text", "") or ""
                        if not s_text.strip():
                            continue
                        spans.append(
                            Span(
                                text=s_text,
                                bbox=tuple(span.get("bbox", (0.0, 0.0, 0.0, 0.0))),
                                page=idx,
                                font=str(span.get("font", "")),
                                size=float(span.get("size", 0.0)),
                            )
                        )
            pages.append(
                ParsedPage(
                    page=idx,
                    text=text,
                    spans=spans,
                    has_text_layer=bool(text.strip()),
                )
            )
            all_text.append(f"[PAGE: {idx}]\n{text}")

        return ParsedPdf(
            page_count=doc.page_count,
            pages=pages,
            full_text="\n".join(all_text),
            is_signed=is_signed,
        )
    finally:
        doc.close()


def _has_digital_signature(doc: fitz.Document) -> bool:
    """Best-effort signature detection — refuses any signed PDF at upload."""
    try:
        if hasattr(doc, "get_signatures"):
            return bool(doc.get_signatures())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    try:
        # Fallback: scan annotations for /Sig widgets.
        for page in doc:
            for annot in page.annots() or []:
                if (annot.type and annot.type[0] == fitz.PDF_ANNOT_WIDGET) and "Sig" in (
                    annot.info.get("subject", "") + annot.info.get("title", "")
                ):
                    return True
    except Exception:  # noqa: BLE001
        return False
    return False


@dataclass
class ExtractedImage:
    """A bitmap embedded in the PDF, with its anchor on the page.

    `bbox` is the rectangle covered by the image in PDF points (top-left
    origin). `caption_nearby` is the nearest line below the image that
    looks like a figure caption (« Figure 1 — … », « Fig. 2: … »).
    """

    page: int  # 1-indexed
    xref: int
    bbox: tuple[float, float, float, float]
    bytes: bytes
    mime: str
    caption_nearby: str


_CAPTION_RE = re.compile(
    r"^\s*(?:figure|fig\.?|illustration)\s*\d+", re.IGNORECASE
)


def _closest_caption(page: "fitz.Page", img_bbox: tuple[float, float, float, float]) -> str:
    """Find the line whose top-Y sits just below the image bbox, looks
    like a figure caption, and is on the same page. Empty string when
    no caption can be detected with reasonable confidence."""
    try:
        data = page.get_text("dict")
    except Exception:  # noqa: BLE001
        return ""
    img_bottom = img_bbox[3]
    best: tuple[float, str] | None = None
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            line_y = float(line.get("bbox", [0, 0, 0, 0])[1])
            if line_y < img_bottom:
                continue
            text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
            if not text or not _CAPTION_RE.match(text):
                continue
            dist = line_y - img_bottom
            if best is None or dist < best[0]:
                best = (dist, text)
    return best[1] if best else ""


def extract_images(path: str | Path, *, max_per_doc: int = 20) -> list[ExtractedImage]:
    """Extract bitmap images embedded in the PDF, with their bbox and
    nearest caption. Capped at `max_per_doc` for cost control on big
    documents — vision calls are paid per image."""
    import fitz  # noqa: PLC0415 — already imported at module top

    doc = fitz.open(str(path))
    try:
        out: list[ExtractedImage] = []
        for page_idx, page in enumerate(doc, start=1):
            if len(out) >= max_per_doc:
                break
            for info in page.get_images(full=True):
                if len(out) >= max_per_doc:
                    break
                xref = info[0]
                # `get_image_bbox` is the only reliable way to know
                # *where* the image renders (xref alone gives only the
                # object). Some PDFs reuse the same xref several times.
                try:
                    bboxes = page.get_image_rects(info)
                except Exception:  # noqa: BLE001
                    bboxes = []
                rect = bboxes[0] if bboxes else page.rect
                bbox = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n - pix.alpha >= 4:  # CMYK → RGB
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_bytes = pix.tobytes("png")
                    pix = None  # release native handle
                except Exception:  # noqa: BLE001
                    continue
                out.append(
                    ExtractedImage(
                        page=page_idx,
                        xref=xref,
                        bbox=bbox,
                        bytes=img_bytes,
                        mime="image/png",
                        caption_nearby=_closest_caption(page, bbox),
                    )
                )
        return out
    finally:
        doc.close()


def locate_with_search_for(
    page: fitz.Page,
    original: str,
    span_index: int,
    reference_bbox: tuple[float, float, float, float] | None = None,
) -> tuple[float, float, float, float] | None:
    """Return the bbox of `original`'s `span_index`-th occurrence on `page`,
    using PyMuPDF's native `page.search_for`. When a precomputed bbox is
    available, prefer the hit that overlaps it so repeated text in another
    page region cannot steal the overlay. None when not found.

    Used by `rules_engine.materialize` to compute precise bboxes for
    suggestion overlays. Pairing the overlay's bbox with the editor's
    locator means « zone surlignée = zone modifiée » by construction
    (both call `page.search_for(original)` with the same `span_index`).
    """
    if not original:
        return None
    try:
        hits = page.search_for(original) or []
    except Exception:  # noqa: BLE001
        return None
    if not hits:
        return None
    if reference_bbox is not None and len(hits) > 1:
        reference = fitz.Rect(*reference_bbox)

        def overlap_ratio(hit: fitz.Rect) -> float:
            intersection = hit & reference
            if intersection.is_empty:
                return 0.0
            smaller_area = min(hit.get_area(), reference.get_area())
            return float(intersection.get_area() / smaller_area) if smaller_area > 0 else 0.0

        ranked = sorted(hits, key=overlap_ratio, reverse=True)
        if overlap_ratio(ranked[0]) > 0:
            rect = ranked[0]
            return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
    idx = max(0, min(span_index, len(hits) - 1))
    rect = hits[idx]
    return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))


def find_span_bbox(page_spans: list[Span], substring: str, start: int, end: int) -> tuple[float, float, float, float]:
    """Legacy span-walk fallback when no `original` text is available
    (e.g. detection-only structural rules). Cheap heuristic kept for
    backward compatibility — prefer `locate_with_search_for` whenever
    the rule has a concrete `original` to match.

    If we can't pin it, return a zeroed bbox — the caller decides whether
    to keep or drop the match.
    """
    cursor = 0
    matched: list[Span] = []
    needle_len = end - start
    for span in page_spans:
        span_text = span.text
        span_start = cursor
        span_end = cursor + len(span_text) + 1  # +1 for the line break we add when joining
        if span_end >= start and span_start <= end:
            matched.append(span)
            collected = sum(len(m.text) for m in matched)
            if collected >= needle_len:
                break
        cursor = span_end
        if cursor > end + len(substring):
            break

    if not matched:
        return (0.0, 0.0, 0.0, 0.0)

    x0 = min(s.bbox[0] for s in matched)
    y0 = min(s.bbox[1] for s in matched)
    x1 = max(s.bbox[2] for s in matched)
    y1 = max(s.bbox[3] for s in matched)
    return (x0, y0, x1, y1)
