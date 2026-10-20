"""Editable text and screenshot rendering for one-pager slides."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def shape_index(slide) -> dict[str, Any]:
    duplicates: set[str] = set()
    index: dict[str, Any] = {}
    def add_shapes(shapes) -> None:
        for shape in shapes:
            if shape.name.startswith("ONEPAGER_") and shape.name in index:
                duplicates.add(shape.name)
            index[shape.name] = shape
            if hasattr(shape, "shapes"):
                add_shapes(shape.shapes)

    add_shapes(slide.shapes)
    if duplicates:
        raise ValueError(f"Duplicate shape names: {', '.join(sorted(duplicates))}")
    return index


def _replace_picture(slide, shape, image_path: Path, name: str) -> None:
    if not image_path.is_file():
        raise ValueError(f"Screenshot does not exist: {image_path}")
    left, top, width, height = shape.left, shape.top, shape.width, shape.height
    shape._element.getparent().remove(shape._element)
    picture = slide.shapes.add_picture(str(image_path), left, top, width, height)
    picture.name = name


def _set_text_preserving_style(shape, value: str) -> None:
    frame = shape.text_frame
    source_paragraph = frame.paragraphs[0]
    source_run = source_paragraph.runs[0] if source_paragraph.runs else None
    paragraph_style = {
        "alignment": source_paragraph.alignment,
        "level": source_paragraph.level,
        "line_spacing": source_paragraph.line_spacing,
        "space_before": source_paragraph.space_before,
        "space_after": source_paragraph.space_after,
    }
    font_style: dict[str, Any] = {}
    if source_run:
        font = source_run.font
        try:
            rgb = font.color.rgb
        except AttributeError:
            rgb = None
        font_style = {
            "name": font.name,
            "size": font.size,
            "bold": font.bold,
            "italic": font.italic,
            "underline": font.underline,
            "rgb": rgb,
        }

    frame.clear()
    for index, line in enumerate(value.splitlines() or [""]):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        for key, setting in paragraph_style.items():
            if setting is not None:
                setattr(paragraph, key, setting)
        run = paragraph.add_run()
        run.text = line
        for key, setting in font_style.items():
            if key != "rgb" and setting is not None:
                setattr(run.font, key, setting)
        if font_style.get("rgb") is not None:
            run.font.color.rgb = font_style["rgb"]


def fill_slide(slide, values, mapping, text_fields) -> None:
    shapes = shape_index(slide)
    missing = [mapping[key] for key in text_fields if mapping[key] not in shapes]
    if missing:
        raise ValueError("Missing mapped text shapes: " + ", ".join(missing))
    for key, value in values.items():
        shape = shapes[mapping[key]]
        if not shape.has_text_frame:
            raise ValueError(f"Mapped shape is not a text shape: {shape.name}")
        _set_text_preserving_style(shape, value)


def fill_screenshots(
    slide, content, content_path, mapping, image_fields
) -> list[str]:
    shapes = shape_index(slide)
    screenshots = content.get("screenshots", {})
    if screenshots and not isinstance(screenshots, dict):
        raise ValueError("'screenshots' must be an object")
    unresolved = []
    for key in image_fields:
        image_value = screenshots.get(key.removeprefix("screenshot_")) if screenshots else None
        shape_name = mapping[key]
        if not image_value:
            unresolved.append(shape_name)
        elif shape_name not in shapes:
            raise ValueError(f"Missing mapped screenshot shape: {shape_name}")
        else:
            image_path = (content_path.parent / image_value).resolve()
            _replace_picture(slide, shapes[shape_name], image_path, shape_name)
    return unresolved
