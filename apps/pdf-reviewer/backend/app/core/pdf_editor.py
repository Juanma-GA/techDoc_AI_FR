"""Apply a structured suggestion to a PDF in place via PyMuPDF.

Strategy
--------

Patch spec : `(page, bbox, original_text, span_index, proposed_text)`.

1. Re-locate the original text on the target page via `page.search_for`.
   If multiple matches, pick the one whose rect overlaps the recorded bbox
   above 60 % (tolerant). If no match → `ORIGINAL_NOT_FOUND`. Ambiguous
   → `BBOX_AMBIGUOUS`.
2. Read the span's font metadata via `page.get_text("dict")` (font name,
   size, color) at the chosen rect.
3. Sample the page background colour at the rect to pick the redact fill
   (instead of pure white), so redactions don't show as bright squares
   on tinted / watermarked pages.
4. Redact the rectangle with the sampled fill, then apply redactions.
5. Insert the proposed text at the same baseline computed from the
   resolved font's ascender metric (not a hardcoded ratio), so the new
   line sits on the same baseline as its neighbours. Fall back to
   Helvetica only when the original font name is unmappable.
6. Save the document with `garbage=4, deflate=True, clean=True`.

Limitations are documented in README "Écarts au standard": kerning,
ligatures, justification and PDF/A conformance are not preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from app.core.errors import AppError


@dataclass
class PatchSpec:
    page: int  # 1-indexed
    bbox: tuple[float, float, float, float]
    original_text: str
    proposed_text: str
    span_index: int = 0


@dataclass
class PatchResult:
    font_used: str
    fallback_used: bool
    length_delta: int
    font_size_used: float = 0.0
    wrapped: bool = False


_FALLBACK_FONT = "helv"
_BBOX_OVERLAP_THRESHOLD = 0.6
_SHRINK_FLOOR = 0.85          # don't shrink below 85 % of the original size
_SHRINK_STEP = 0.95
_OVERFLOW_TOLERANCE = 1.05    # accept text 5 % wider before any shrink kicks in

# Approximate vertical metrics for PyMuPDF's 14 built-in fonts. Used as
# fallback when we can't query the original font's metrics directly.
# Numbers are em-relative (multiply by font_size to get points).
_BUILTIN_ASCENDER = {
    "helv": 0.718, "heli": 0.718, "hebo": 0.718, "hebi": 0.718,
    "times-roman": 0.683, "timi": 0.683, "tibo": 0.683, "tibi": 0.683,
    "cour": 0.629, "coui": 0.629, "cobo": 0.629, "cobi": 0.629,
    "symb": 0.683, "zadb": 0.700,
}
_BUILTIN_DESCENDER = {
    "helv": -0.207, "heli": -0.207, "hebo": -0.207, "hebi": -0.207,
    "times-roman": -0.217, "timi": -0.217, "tibo": -0.217, "tibi": -0.217,
    "cour": -0.157, "coui": -0.157, "cobo": -0.157, "cobi": -0.157,
    "symb": -0.217, "zadb": -0.200,
}


def _rect_overlap_ratio(a: fitz.Rect, b: fitz.Rect) -> float:
    inter = a & b
    if inter.is_empty:
        return 0.0
    smaller = min(a.get_area(), b.get_area())
    return float(inter.get_area() / smaller) if smaller > 0 else 0.0


def _find_span_font(page: fitz.Page, rect: fitz.Rect) -> tuple[str, float, tuple[float, float, float]]:
    """Best-effort lookup of the span's font/size/color overlapping `rect`."""
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_rect = fitz.Rect(span["bbox"])
                if _rect_overlap_ratio(span_rect, rect) > 0.4:
                    color_int = int(span.get("color", 0))
                    r = ((color_int >> 16) & 0xFF) / 255.0
                    g = ((color_int >> 8) & 0xFF) / 255.0
                    b = (color_int & 0xFF) / 255.0
                    return str(span.get("font", _FALLBACK_FONT)), float(span["size"]), (r, g, b)
    return _FALLBACK_FONT, 11.0, (0.0, 0.0, 0.0)


def _resolve_font(font_name: str) -> tuple[str, bool]:
    """Map a span font name to one of PyMuPDF's built-in font ids.

    Recognises common weight / style suffixes so a bold or italic span
    keeps its weight instead of collapsing onto plain Helvetica. The
    returned id is one of PyMuPDF's built-in alias strings (`helv`,
    `hebo`, `times-roman`, `tibi`, `cour`…)."""
    base = (font_name or "").lower()
    is_bold = any(t in base for t in ("bold", "black", "heavy", "extrabold"))
    is_italic = any(t in base for t in ("italic", "oblique", "slanted"))
    if "times" in base or "serif" in base or "tex" in base or "garamond" in base:
        if is_bold and is_italic:
            return "tibi", False
        if is_bold:
            return "tibo", False
        if is_italic:
            return "timi", False
        return "times-roman", False
    if "courier" in base or "mono" in base or "consolas" in base:
        if is_bold and is_italic:
            return "cobi", False
        if is_bold:
            return "cobo", False
        if is_italic:
            return "coui", False
        return "cour", False
    # Treat Arial / Helvetica / generic sans-serif as Helvetica with weight.
    if is_bold and is_italic:
        return "hebi", False
    if is_bold:
        return "hebo", False
    if is_italic:
        return "heli", False
    return _FALLBACK_FONT, base != "" and base != _FALLBACK_FONT


def _font_metrics(font_id: str) -> tuple[float, float]:
    """Return `(ascender, descender)` for the resolved font id, em-relative."""
    return (
        _BUILTIN_ASCENDER.get(font_id, 0.718),
        _BUILTIN_DESCENDER.get(font_id, -0.207),
    )


def _sample_background(page: fitz.Page, rect: fitz.Rect) -> tuple[float, float, float]:
    """Sample the page colour just *outside* the redact rect to pick a
    fill that blends with the surrounding background. Returns RGB in
    [0, 1]. Falls back to pure white when sampling can't establish a
    stable colour (e.g. the rect butts against page edges)."""
    page_rect = page.rect
    margin = max(3.0, min(rect.height, rect.width) * 0.5)
    candidates: list[fitz.Rect] = []
    # Right of the rect
    if rect.x1 + margin < page_rect.x1:
        candidates.append(fitz.Rect(rect.x1 + 1, rect.y0, rect.x1 + margin, rect.y1))
    # Left of the rect
    if rect.x0 - margin > page_rect.x0:
        candidates.append(fitz.Rect(rect.x0 - margin, rect.y0, rect.x0 - 1, rect.y1))
    # Above the rect
    if rect.y0 - margin > page_rect.y0:
        candidates.append(fitz.Rect(rect.x0, rect.y0 - margin, rect.x1, rect.y0 - 1))
    # Below the rect
    if rect.y1 + margin < page_rect.y1:
        candidates.append(fitz.Rect(rect.x0, rect.y1 + 1, rect.x1, rect.y1 + margin))

    samples: list[tuple[int, int, int]] = []
    for clip in candidates:
        try:
            pix = page.get_pixmap(clip=clip, alpha=False)
        except Exception:  # noqa: BLE001
            continue
        if pix.width == 0 or pix.height == 0:
            continue
        # Pick the middle pixel of the clip — cheap, avoids edge artefacts.
        px = pix.width // 2
        py = pix.height // 2
        try:
            r, g, b = pix.pixel(px, py)[:3]
        except Exception:  # noqa: BLE001
            continue
        samples.append((r, g, b))

    if not samples:
        return (1.0, 1.0, 1.0)
    # Use the brightest sample (page background is usually the lightest
    # colour around glyphs). Avoids picking up an accidental adjacent glyph.
    r, g, b = max(samples, key=lambda s: s[0] + s[1] + s[2])
    return (r / 255.0, g / 255.0, b / 255.0)


def _find_line_for_rect(
    page: fitz.Page, target: fitz.Rect
) -> tuple[fitz.Rect, str] | None:
    """Locate the text line containing `target`. Returns (line_rect, line_text)
    or None when the surrounding line cannot be reconstructed (e.g. raster
    page or unsupported PDF structure)."""
    data = page.get_text("dict")
    best: tuple[fitz.Rect, str, float] | None = None
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            line_rect = fitz.Rect(line["bbox"])
            score = _rect_overlap_ratio(target, line_rect)
            if score < 0.5:
                continue
            line_text = "".join(s.get("text", "") for s in spans)
            if best is None or score > best[2]:
                best = (line_rect, line_text, score)
    if best is None:
        return None
    return best[0], best[1]


def _are_rects_contiguous(rects: list[fitz.Rect]) -> bool:
    """True when `rects` form a vertical run (a multi-line phrase): each
    successive rect sits below the previous one within ~2 line heights."""
    if len(rects) <= 1:
        return True
    ordered = sorted(rects, key=lambda r: (r.y0, r.x0))
    for prev, nxt in zip(ordered, ordered[1:]):
        prev_h = max(prev.height, 1.0)
        if nxt.y0 < prev.y0 - 0.5:           # not strictly descending
            return False
        if nxt.y0 - prev.y1 > prev_h * 1.5:  # gap too large between lines
            return False
    return True


def apply_patch(src: Path, dst: Path, patch: PatchSpec) -> PatchResult:
    """Apply `patch` to `src`, write the result to `dst`. Idempotent at the
    caller level (Suggestion.status == 'applied' should gate re-entry).

    Supports both single-span and multi-line phrase replacements:
    - When `page.search_for(original)` returns one rect, redact the line
      containing it and re-render the full line with the substitution.
    - When it returns several contiguous rects (typical of a sentence
      that wraps over 2-3 lines), redact the whole zone and re-render
      the proposed text in a textbox covering their union."""
    if not src.is_file():
        raise AppError("PDF_VERSION_MISSING", f"PDF source absent: {src}", status_code=500)

    doc = fitz.open(src)
    try:
        if patch.page < 1 or patch.page > doc.page_count:
            raise AppError(
                "PDF_PAGE_OUT_OF_RANGE",
                f"Page {patch.page} hors limites (1..{doc.page_count})",
                status_code=400,
            )

        page = doc[patch.page - 1]
        recorded = fitz.Rect(*patch.bbox)
        hits = page.search_for(patch.original_text) or []

        if not hits:
            raise AppError(
                "ORIGINAL_NOT_FOUND",
                "Texte original introuvable sur la page (PDF déjà modifié ?)",
                status_code=409,
                detail={"page": patch.page, "original": patch.original_text},
            )

        # Multi-line phrase: search_for returns one rect per line. We treat
        # the whole run as a single edit zone.
        multi_line = len(hits) > 1 and _are_rects_contiguous(hits)

        chosen: fitz.Rect | None = None
        all_rects: list[fitz.Rect] = hits
        if multi_line:
            # Use the union as the visual anchor for font/color lookup; we
            # still redact each rect individually below.
            chosen = fitz.Rect(hits[0])
            for r in hits[1:]:
                chosen.include_rect(r)
        elif len(hits) == 1:
            chosen = hits[0]
            all_rects = [chosen]
        else:
            ranked = sorted(
                hits,
                key=lambda r: _rect_overlap_ratio(r, recorded),
                reverse=True,
            )
            top = ranked[0]
            second = ranked[1] if len(ranked) > 1 else None
            top_score = _rect_overlap_ratio(top, recorded)
            if top_score < _BBOX_OVERLAP_THRESHOLD:
                if patch.span_index < len(hits):
                    chosen = hits[patch.span_index]
                else:
                    raise AppError(
                        "BBOX_AMBIGUOUS",
                        "Plusieurs occurrences trouvées, bbox insuffisant pour trancher",
                        status_code=409,
                        detail={"page": patch.page, "matches": len(hits)},
                    )
            elif second is not None and _rect_overlap_ratio(second, recorded) > top_score - 0.05:
                raise AppError(
                    "BBOX_AMBIGUOUS",
                    "Plusieurs occurrences avec bbox similaire — édition refusée",
                    status_code=409,
                    detail={"page": patch.page, "matches": len(hits)},
                )
            else:
                chosen = top
            all_rects = [chosen]

        assert chosen is not None
        font_name, font_size, color = _find_span_font(page, chosen)
        resolved_font, fallback = _resolve_font(font_name)

        if multi_line:
            # Redact every line individually (avoids carving columns into
            # the rest of the page), then insert the proposed text in a
            # textbox covering the union — `insert_textbox` wraps as needed.
            for r in all_rects:
                fill = _sample_background(page, r)
                page.add_redact_annot(r, fill=fill)
            page.apply_redactions()
            redact_rect = chosen   # union, used for sizing only
            insert_text = patch.proposed_text
        else:
            # Single-line: redact the FULL line so the surrounding words
            # don't end up half-erased, and re-render the full line text
            # with the substitution applied.
            line = _find_line_for_rect(page, chosen)
            if line is not None and patch.original_text in line[1]:
                redact_rect, line_text = line
                insert_text = line_text.replace(patch.original_text, patch.proposed_text, 1)
            else:
                redact_rect = chosen
                insert_text = patch.proposed_text

        target_w = float(redact_rect.width)
        target_h = float(redact_rect.height)

        # Pick the largest font_size that fits the rect; floor at 85 % to
        # keep the line readable.
        size_used = font_size
        text_w = fitz.get_text_length(insert_text, fontname=resolved_font, fontsize=size_used)
        floor = font_size * _SHRINK_FLOOR
        while text_w > target_w * _OVERFLOW_TOLERANCE and size_used > floor:
            size_used *= _SHRINK_STEP
            text_w = fitz.get_text_length(insert_text, fontname=resolved_font, fontsize=size_used)

        wrapped = False
        if not multi_line:
            # Single-line edits still need an explicit redact (multi-line
            # already redacted each rect above).
            fill = _sample_background(page, redact_rect)
            page.add_redact_annot(redact_rect, fill=fill)
            page.apply_redactions()

        if not multi_line and text_w <= target_w * _OVERFLOW_TOLERANCE:
            # Baseline = top + ascender * font_size, calibrated on the
            # resolved font's metrics. Falls back to the historic 0.78 ×
            # height ratio if both the rect height and the metric look
            # off (defence in depth).
            ascender, _ = _font_metrics(resolved_font)
            baseline_y = redact_rect.y0 + ascender * size_used
            if not (redact_rect.y0 < baseline_y < redact_rect.y1):
                baseline_y = redact_rect.y0 + (target_h * 0.78)
            page.insert_text(
                (redact_rect.x0, baseline_y),
                insert_text,
                fontname=resolved_font,
                fontsize=size_used,
                color=color,
                render_mode=0,
            )
        else:
            # Multi-line edits, or a single-line edit that overflows: render
            # the proposed text in a textbox that covers the redacted zone
            # (extended by one line height for single-line overflow cases
            # so the wrap has somewhere to land).
            if multi_line:
                wrap_rect = redact_rect
            else:
                wrap_rect = fitz.Rect(
                    redact_rect.x0,
                    redact_rect.y0,
                    redact_rect.x1,
                    redact_rect.y0 + 2 * target_h,
                )
            wrapped = True
            leftover = page.insert_textbox(
                wrap_rect,
                insert_text,
                fontname=resolved_font,
                fontsize=size_used,
                color=color,
                align=fitz.TEXT_ALIGN_LEFT,
            )
            if leftover < 0:
                raise AppError(
                    "EDIT_OVERFLOW",
                    "Le texte proposé ne tient pas dans la zone disponible.",
                    status_code=409,
                    detail={
                        "page": patch.page,
                        "original_len": len(patch.original_text),
                        "proposed_len": len(patch.proposed_text),
                    },
                )

        doc.save(str(dst), garbage=4, deflate=True, clean=True)
    finally:
        doc.close()

    return PatchResult(
        font_used=resolved_font,
        fallback_used=fallback,
        length_delta=len(patch.proposed_text) - len(patch.original_text),
        font_size_used=size_used,
        wrapped=wrapped,
    )
