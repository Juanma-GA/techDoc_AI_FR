"""Extract and tag the ATEXIS bilingual one-pager reference slides."""
from __future__ import annotations

import argparse
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from slides import clone_slide, reorder_slides, retain_slides


SHAPE_NAMES = {
    0: "ONEPAGER_MAIN_TITLE",
    8: "ONEPAGER_STATUS",
    11: "ONEPAGER_APP_NAME",
    16: "ONEPAGER_CALLOUT_1",
    17: "ONEPAGER_CALLOUT_2",
    18: "ONEPAGER_CALLOUT_3",
    24: "ONEPAGER_LOCAL_SECURITY",
    25: "ONEPAGER_SHARED_SECURITY",
    27: "ONEPAGER_CHALLENGE",
    28: "ONEPAGER_SOLUTION",
    29: "ONEPAGER_FEATURES",
}


def _remove(shape) -> None:
    shape.element.getparent().remove(shape.element)


def _replace_text(shape, value: str) -> None:
    paragraph = shape.text_frame.paragraphs[0]
    if paragraph.runs:
        paragraph.runs[0].text = value
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = value


def _add_placeholder(slide, source, name: str) -> None:
    placeholder = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, source.left, source.top, source.width, source.height
    )
    placeholder.name = name
    placeholder.fill.solid()
    placeholder.fill.fore_color.rgb = RGBColor(0x0D, 0x1F, 0x46)
    placeholder.line.color.rgb = RGBColor(0x36, 0xB9, 0xE8)
    placeholder.line.width = Pt(1)
    frame = placeholder.text_frame
    frame.clear()
    paragraph = frame.paragraphs[0]
    paragraph.alignment = 1
    run = paragraph.add_run()
    run.text = "SCREENSHOT"
    run.font.name = "Arial"
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def _add_footnote(slide) -> None:
    shape = slide.shapes.add_textbox(
        Inches(4.75), Inches(7.10), Inches(6.15), Inches(0.18)
    )
    shape.name = "ONEPAGER_FOOTNOTE"
    frame = shape.text_frame
    frame.clear()
    frame.margin_left = frame.margin_right = 0
    frame.margin_top = frame.margin_bottom = 0
    paragraph = frame.paragraphs[0]
    paragraph.alignment = 1
    run = paragraph.add_run()
    run.text = "LIMITATION"
    run.font.name = "Arial"
    run.font.size = Pt(5.5)
    run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def _prepare_slide(slide, language: str) -> None:
    shapes = list(slide.shapes)
    if language == "fr":
        _replace_text(shapes[5], "DÉFI")
        _replace_text(shapes[7], "SOLUTION")
        _replace_text(shapes[13], "FONCTIONNALITÉS")
        _replace_text(shapes[23], "SÉCURITÉ")
        _replace_text(shapes[26], "Application partagée sur site")
        _replace_text(shapes[30], "Application locale")
    for index, name in SHAPE_NAMES.items():
        shapes[index].name = name
    section_title = shapes[1].shapes[0]
    section_title.name = "ONEPAGER_SECTION_TITLE"
    if language == "fr":
        shapes[13].width = Inches(2.60)
        shapes[28].top += Inches(0.08)
        shapes[28].height -= Inches(0.08)
        shapes[29].top += Inches(0.10)
        shapes[29].height -= Inches(0.10)

    _add_placeholder(slide, shapes[15], "ONEPAGER_SCREENSHOT_TOP")
    _add_placeholder(slide, shapes[14], "ONEPAGER_SCREENSHOT_BOTTOM")
    for index in (14, 15, 19, 20, 21):
        _remove(shapes[index])
    _add_footnote(slide)


def build(source: Path, output: Path, reference_slide: int) -> None:
    presentation = Presentation(source)
    if reference_slide > len(presentation.slides):
        raise ValueError("Reference slide number does not exist")
    english = presentation.slides[reference_slide - 1]
    french = clone_slide(presentation, english)
    retain_slides(presentation, [french, english])
    reorder_slides(presentation, [french, english])
    _prepare_slide(french, "fr")
    _prepare_slide(english, "en")
    output.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(output)
    print(f"Built reference template: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-slide", type=int, default=19)
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve(), args.reference_slide)


if __name__ == "__main__":
    main()
