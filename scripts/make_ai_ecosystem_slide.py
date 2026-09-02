"""Generate the one-slide ATEXIS AI ecosystem overview."""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ECOSYSTEME_IA_ATEXIS.pptx"

BG = RGBColor(0x0E, 0x11, 0x17)
PANEL = RGBColor(0x16, 0x1C, 0x2B)
PANEL_2 = RGBColor(0x1D, 0x25, 0x40)
TEXT = RGBColor(0xE2, 0xE8, 0xF0)
MUTED = RGBColor(0x94, 0xA3, 0xB8)
BLUE = RGBColor(0x25, 0x63, 0xEB)
BLUE_2 = RGBColor(0x3B, 0x82, 0xF6)
GREEN = RGBColor(0x34, 0xD3, 0x99)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)
VIOLET = RGBColor(0x9A, 0x8B, 0xFF)
LINE = RGBColor(0x32, 0x3B, 0x4F)


def rect(slide, x, y, w, h, fill=PANEL, line=LINE, radius=True):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line
    shape.line.width = Pt(0.8)
    shape.shadow.inherit = False
    if radius:
        shape.adjustments[0] = 0.08
    return shape


def text(slide, value, x, y, w, h, size=12, color=TEXT, bold=False,
         font="Inter", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(0.03)
    frame.margin_top = frame.margin_bottom = 0
    frame.vertical_anchor = anchor
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = value
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def line(slide, x1, y1, x2, y2, color=LINE, width=1.0):
    connector = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    connector.line.color.rgb = color
    connector.line.width = Pt(width)
    return connector


def pill(slide, label, x, y, w, color):
    rect(slide, x, y, w, 0.26, fill=PANEL_2, line=color)
    dot = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, Inches(x + 0.09), Inches(y + 0.085), Inches(0.09), Inches(0.09)
    )
    dot.fill.solid()
    dot.fill.fore_color.rgb = color
    dot.line.fill.background()
    text(slide, label, x + 0.22, y + 0.035, w - 0.27, 0.17, size=7.4, bold=True)


def add_maturity(slide):
    levels = [
        ("01", "HUMAN-AGENT", "Aujourd'hui", "Assistance spécialisée\nValidation humaine critique"),
        ("02", "MULTI-AGENTS", "Prochain palier", "Workflows reliés\nTraçables et pilotables"),
        ("03", "AUTONOMIE CONTRÔLÉE", "Cible", "Cas répétitifs à faible risque\nGarde-fous systématiques"),
    ]
    x_positions = [4.62, 7.35, 10.08]
    for index, ((number, title_value, badge, body), x) in enumerate(zip(levels, x_positions)):
        rect(slide, x, 0.95, 2.45, 1.05, fill=PANEL)
        text(slide, number, x + 0.16, 1.08, 0.34, 0.22, size=9, color=BLUE_2, bold=True, font="JetBrains Mono")
        text(slide, title_value, x + 0.51, 1.05, 1.78, 0.25, size=10.2, bold=True, font="Orbitron")
        text(slide, badge.upper(), x + 0.16, 1.39, 0.9, 0.16, size=6.8, color=BLUE_2, bold=True, font="JetBrains Mono")
        text(slide, body, x + 0.16, 1.58, 2.12, 0.32, size=8.2, color=MUTED)
        if index < 2:
            arrow = slide.shapes.add_shape(
                MSO_SHAPE.CHEVRON, Inches(x + 2.50), Inches(1.34), Inches(0.18), Inches(0.25)
            )
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = BLUE
            arrow.line.fill.background()


def add_stage(slide, number, title_value, outcome, apps, x):
    rect(slide, x, 2.64, 2.38, 3.78, fill=PANEL)
    accent = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(x), Inches(2.64), Inches(2.38), Inches(0.055)
    )
    accent.fill.solid()
    accent.fill.fore_color.rgb = BLUE
    accent.line.fill.background()

    circle = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, Inches(x + 0.16), Inches(2.87), Inches(0.38), Inches(0.38)
    )
    circle.fill.solid()
    circle.fill.fore_color.rgb = BLUE
    circle.line.fill.background()
    text(slide, number, x + 0.16, 2.95, 0.38, 0.16, size=8.5, bold=True,
         align=PP_ALIGN.CENTER)
    text(slide, title_value, x + 0.16, 3.39, 2.04, 0.58, size=12.2, bold=True, font="Orbitron")
    text(slide, outcome, x + 0.16, 4.08, 2.04, 0.62, size=8.8, color=MUTED)

    y = 4.92
    for label, status in apps:
        pill(slide, label, x + 0.16, y, 2.04, status)
        y += 0.34


def build():
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    background = slide.background.fill
    background.solid()
    background.fore_color.rgb = BG

    text(slide, "AI4TECHDOC", 0.56, 0.34, 3.1, 0.32, size=11, color=BLUE_2,
         bold=True, font="JetBrains Mono")
    text(slide, "ÉCOSYSTÈME IA", 0.56, 0.72, 3.55, 0.58, size=28, bold=True, font="Orbitron")
    text(slide, "De la donnée technique brute à la livraison documentaire sécurisée",
         0.56, 1.37, 3.35, 0.58, size=12, color=MUTED)
    text(slide, "10 APPLICATIONS", 0.56, 2.14, 1.43, 0.22, size=8, color=TEXT,
         bold=True, font="JetBrains Mono")
    text(slide, "8 ACTIVES", 2.04, 2.14, 0.95, 0.22, size=8, color=GREEN,
         bold=True, font="JetBrains Mono")
    text(slide, "2 À VALIDER", 3.02, 2.14, 1.12, 0.22, size=8, color=AMBER,
         bold=True, font="JetBrains Mono")

    add_maturity(slide)
    line(slide, 0.56, 2.43, 12.77, 2.43, color=LINE, width=0.8)

    stages = [
        ("01", "ANALYSER & STRUCTURER", "Du legacy vers des actifs numériques structurés et réutilisables.",
         [("OCR Vision", GREEN), ("S1000D Extractor", GREEN)]),
        ("02", "RÉDIGER & TRADUIRE", "Accélérer la production multilingue avec cohérence terminologique.",
         [("Doc Writer", GREEN), ("A³ Linguo", VIOLET)]),
        ("03", "ILLUSTRER & ANNOTER", "Synchroniser textes, images et repères avec moins de reprises.",
         [("Catia Toolbox", GREEN), ("ImageBot AI", VIOLET)]),
        ("04", "VALIDER & QUALIFIER", "Détecter plus tôt incohérences, conflits et non-conformités.",
         [("Corpus Agent", GREEN), ("Doc Reviewer", GREEN), ("BRDP Manager", AMBER), ("XML Proofreader", AMBER)]),
        ("05", "PUBLIER & LIVRER", "Livrer des packages validés avec qualité, sécurité et traçabilité.",
         [("Capacité à construire", MUTED)]),
    ]
    for stage, x in zip(stages, [0.56, 3.05, 5.54, 8.03, 10.52]):
        add_stage(slide, *stage, x)

    for x in [2.94, 5.43, 7.92, 10.41]:
        arrow = slide.shapes.add_shape(
            MSO_SHAPE.CHEVRON, Inches(x), Inches(4.28), Inches(0.10), Inches(0.25)
        )
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = BLUE_2
        arrow.line.fill.background()

    text(slide, "TRAJECTOIRE DE MATURITÉ", 4.62, 0.57, 3.15, 0.2, size=7.8,
         color=MUTED, bold=True, font="JetBrains Mono")
    text(slide, "PROCESS CIBLE EN 5 PILIERS", 0.56, 6.68, 2.55, 0.2, size=7.8,
         color=MUTED, bold=True, font="JetBrains Mono")
    pill(slide, "Active", 8.95, 6.65, 0.95, GREEN)
    pill(slide, "À valider", 10.02, 6.65, 1.14, AMBER)
    pill(slide, "Externe", 11.28, 6.65, 1.02, VIOLET)
    text(slide, "Humain dans la boucle • Orchestration traçable • Autonomie sous gouvernance",
         0.56, 7.04, 8.2, 0.2, size=9.2, color=TEXT, bold=True)
    text(slide, "Source : portail AI4TECHDOC", 10.55, 7.04, 2.22, 0.18, size=7.5,
         color=MUTED, align=PP_ALIGN.RIGHT)

    presentation.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    result = build()
    print(f"OK: {result} ({result.stat().st_size:,} bytes)")