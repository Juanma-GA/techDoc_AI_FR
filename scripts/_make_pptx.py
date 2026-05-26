"""One-off : ARCHITECTURE_POC.pptx — minimalist business deck (English).

4 slides, plain rectangles, minimal palette (3 colors), no emoji, plain bullets.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

DST = Path("ARCHITECTURE_POC.pptx")

# 3-color palette
TEXT = RGBColor(0x1F, 0x29, 0x37)
DIM = RGBColor(0x6B, 0x72, 0x80)
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
HAIRLINE = RGBColor(0xD1, 0xD5, 0xDB)


def _fill(shape, rgb: RGBColor | None) -> None:
    if rgb is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb


def _line(shape, rgb: RGBColor | None, width_pt: float = 0.75) -> None:
    if rgb is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = rgb
        shape.line.width = Pt(width_pt)


def add_text(
    slide,
    x: float, y: float, w: float, h: float,
    runs: list[tuple[str, dict]],
    align: int = PP_ALIGN.LEFT,
    anchor: int = MSO_ANCHOR.TOP,
):
    """runs = [(text, {size, bold, color, name})]; each run is its own paragraph
    if it ends with '\\n' (rough but predictable)."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.word_wrap = True
    tf.vertical_anchor = anchor

    p = tf.paragraphs[0]
    p.alignment = align
    first = True
    for text, fmt in runs:
        if not first:
            p = tf.add_paragraph()
            p.alignment = align
            p.space_before = Pt(fmt.get("space_before", 0))
        first = False
        r = p.add_run()
        r.text = text
        r.font.size = Pt(fmt.get("size", 12))
        r.font.bold = fmt.get("bold", False)
        r.font.italic = fmt.get("italic", False)
        r.font.name = fmt.get("name", "Calibri")
        r.font.color.rgb = fmt.get("color", TEXT)
    return box


def add_rect(slide, x, y, w, h, fill: RGBColor | None = None, border: RGBColor | None = HAIRLINE, width_pt: float = 0.75):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    _fill(shape, fill)
    _line(shape, border, width_pt)
    shape.shadow.inherit = False
    return shape


def add_line(slide, x1, y1, x2, y2, color: RGBColor = HAIRLINE, width_pt: float = 0.75):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    conn.line.color.rgb = color
    conn.line.width = Pt(width_pt)
    return conn


def slide_title(slide, text: str):
    add_text(
        slide, 0.6, 0.45, 12.1, 0.7,
        [(text, {"size": 26, "bold": True, "color": TEXT, "name": "Calibri"})],
    )
    # Hairline under title
    add_line(slide, 0.6, 1.15, 12.7, 1.15, color=HAIRLINE, width_pt=0.5)


def bullets(parent_runs: list[tuple[str, dict]], items: list[str], size: int = 12, indent: bool = True) -> None:
    for i, item in enumerate(items):
        prefix = "·   " if indent else ""
        parent_runs.append(
            (prefix + item, {"size": size, "color": TEXT, "name": "Calibri",
                             "space_before": 6 if i == 0 else 4})
        )


# ─── Slide 1 ─────────────────────────────────────────────────────────────────
def slide_1(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_title(slide, "A shared toolkit for all our POCs")

    # Central box
    add_rect(slide, 3.5, 2.0, 6.3, 1.7, fill=None, border=ACCENT, width_pt=1.5)
    add_text(
        slide, 3.5, 2.0, 6.3, 1.7,
        [
            ("Shared toolkit", {"size": 22, "bold": True, "color": ACCENT, "name": "Calibri"}),
            ("Visual identity   ·   Interface components   ·   Quality standards",
             {"size": 13, "color": TEXT, "name": "Calibri", "space_before": 14}),
        ],
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
    )

    # POC tiles
    pocs = ["POC 1", "POC 2", "POC 3", "POC 4", "..."]
    n = len(pocs)
    tile_w = 1.7
    gap = 0.4
    total = n * tile_w + (n - 1) * gap
    start = (13.333 - total) / 2
    tile_y = 5.0
    tile_h = 0.9

    for i, name in enumerate(pocs):
        x = start + i * (tile_w + gap)
        # connector
        add_line(slide, x + tile_w / 2, 3.7, x + tile_w / 2, tile_y, color=HAIRLINE, width_pt=0.75)
        # tile
        add_rect(slide, x, tile_y, tile_w, tile_h, fill=None, border=HAIRLINE)
        add_text(
            slide, x, tile_y, tile_w, tile_h,
            [(name, {"size": 14, "bold": True, "color": TEXT, "name": "Calibri"})],
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
        )

    # Bottom note (single line, dim)
    add_text(
        slide, 0.6, 6.5, 12.1, 0.4,
        [("Each POC stays independent. Improving the toolkit improves every POC.",
          {"size": 12, "italic": True, "color": DIM, "name": "Calibri"})],
        align=PP_ALIGN.CENTER,
    )


# ─── Slide 2 ─────────────────────────────────────────────────────────────────
def slide_2(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_title(slide, "What is shared across all POCs")

    cols = [
        ("Visual identity",
         "Colors, typography, light and dark mode, spacing.",
         ["Same look on every POC.",
          "A palette change applies everywhere.",
          "No per-POC styling work."]),
        ("Interface components",
         "Buttons, cards, dialogs, forms, indicators.",
         ["Users moving between POCs find the same elements.",
          "No relearning between cases.",
          "Less time spent on UI plumbing."]),
        ("Quality standards",
         "Security, automated tests, code structure, error handling.",
         ["Same reliability baseline on every POC.",
          "Compliance checked before each commit.",
          "Predictable behavior in front of stakeholders."]),
    ]

    col_w = 3.9
    gap = 0.25
    total = 3 * col_w + 2 * gap
    start = (13.333 - total) / 2
    col_y = 1.5
    col_h = 5.0

    for i, (title, sub, items) in enumerate(cols):
        x = start + i * (col_w + gap)
        # accent top hairline
        add_rect(slide, x, col_y, col_w, 0.04, fill=ACCENT, border=ACCENT, width_pt=0.5)
        # title + body
        runs: list[tuple[str, dict]] = [
            (title, {"size": 17, "bold": True, "color": TEXT, "name": "Calibri",
                     "space_before": 0}),
            (sub, {"size": 12, "italic": True, "color": DIM, "name": "Calibri",
                   "space_before": 6}),
        ]
        bullets(runs, items, size=12)
        add_text(slide, x + 0.05, col_y + 0.2, col_w - 0.1, col_h - 0.3, runs)


# ─── Slide 3 ─────────────────────────────────────────────────────────────────
def slide_3(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_title(slide, "What is specific to each POC")

    cols = [
        ("Business logic",
         "Analysis rules, controls, processing tied to the use case.",
         ["FTM v2: validation rules for technical documents.",
          "PDF Reviewer: S1000D anomaly detection, unit conversion.",
          "Lives only inside the POC's own folder."]),
        ("Dedicated screens",
         "Dashboards, business views, workflows tailored to the user.",
         ["Each POC owns its pages and its information architecture.",
          "The shell (sidebar, header, navigation) stays shared.",
          "No layout decisions reinvented per POC."]),
        ("Data",
         "Each POC has its own database, isolated from the others.",
         ["A POC never reads or writes another POC's data.",
          "Removing a POC has zero impact on the rest.",
          "Each dataset stays scoped to its own purpose."]),
    ]

    col_w = 3.9
    gap = 0.25
    total = 3 * col_w + 2 * gap
    start = (13.333 - total) / 2
    col_y = 1.5
    col_h = 5.0

    for i, (title, sub, items) in enumerate(cols):
        x = start + i * (col_w + gap)
        add_rect(slide, x, col_y, col_w, 0.04, fill=ACCENT, border=ACCENT, width_pt=0.5)
        runs: list[tuple[str, dict]] = [
            (title, {"size": 17, "bold": True, "color": TEXT, "name": "Calibri",
                     "space_before": 0}),
            (sub, {"size": 12, "italic": True, "color": DIM, "name": "Calibri",
                   "space_before": 6}),
        ]
        bullets(runs, items, size=12)
        add_text(slide, x + 0.05, col_y + 0.2, col_w - 0.1, col_h - 0.3, runs)


# ─── Slide 4 ─────────────────────────────────────────────────────────────────
def slide_4(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_title(slide, "Why this approach")

    items = [
        ("Speed",
         "A new POC starts from a ready-made canvas, not from scratch."),
        ("Consistency",
         "Moving from one POC to another feels familiar to every user."),
        ("Maintainability",
         "A fix or improvement on the toolkit benefits every POC at once."),
        ("Compounding",
         "What we learn on one POC carries over directly to the next."),
    ]

    cell_w = 5.9
    cell_h = 2.3
    gap_x = 0.4
    gap_y = 0.4
    start_x = (13.333 - 2 * cell_w - gap_x) / 2
    start_y = 1.5

    for i, (h, body) in enumerate(items):
        col = i % 2
        row = i // 2
        x = start_x + col * (cell_w + gap_x)
        y = start_y + row * (cell_h + gap_y)
        # hairline left edge
        add_rect(slide, x, y, 0.04, cell_h, fill=ACCENT, border=ACCENT, width_pt=0.5)
        add_text(
            slide, x + 0.25, y + 0.25, cell_w - 0.4, cell_h - 0.5,
            [
                (h, {"size": 22, "bold": True, "color": TEXT, "name": "Calibri"}),
                (body, {"size": 14, "color": DIM, "name": "Calibri", "space_before": 10}),
            ],
        )


def main() -> int:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    slide_1(prs)
    slide_2(prs)
    slide_3(prs)
    slide_4(prs)

    prs.save(DST)
    print(f"OK : {DST} ({DST.stat().st_size:,} bytes, {len(prs.slides)} slides)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
