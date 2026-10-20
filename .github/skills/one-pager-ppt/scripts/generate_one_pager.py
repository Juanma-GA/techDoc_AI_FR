"""Fill an editable one-pager PowerPoint template from structured JSON."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from content import bilingual_content, read_json
from render import fill_screenshots, fill_slide
from slides import clone_slide, retain_slides

try:
    from pptx import Presentation
except ImportError as exc:  # pragma: no cover - environment-specific
    raise SystemExit(
        "python-pptx is required. Install it in an isolated environment with "
        "'python -m pip install python-pptx'."
    ) from exc


TEXT_FIELDS = {
    "main_title": "ONEPAGER_MAIN_TITLE",
    "section_title": "ONEPAGER_SECTION_TITLE",
    "application_name": "ONEPAGER_APP_NAME",
    "status": "ONEPAGER_STATUS",
    "challenge": "ONEPAGER_CHALLENGE",
    "solution": "ONEPAGER_SOLUTION",
    "features": "ONEPAGER_FEATURES",
    "callout_1": "ONEPAGER_CALLOUT_1",
    "callout_2": "ONEPAGER_CALLOUT_2",
    "callout_3": "ONEPAGER_CALLOUT_3",
    "local_security": "ONEPAGER_LOCAL_SECURITY",
    "shared_security": "ONEPAGER_SHARED_SECURITY",
    "footnote": "ONEPAGER_FOOTNOTE",
}
IMAGE_FIELDS = {
    "screenshot_top": "ONEPAGER_SCREENSHOT_TOP",
    "screenshot_bottom": "ONEPAGER_SCREENSHOT_BOTTOM",
}

def inspect_template(template: Path, slide_number: int) -> None:
    presentation = Presentation(template)
    if not 1 <= slide_number <= len(presentation.slides):
        raise ValueError(f"Slide {slide_number} does not exist")
    slide = presentation.slides[slide_number - 1]
    print(f"Slides: {len(presentation.slides)}; inspecting slide: {slide_number}")
    for shape in slide.shapes:
        text = shape.text.replace("\n", " | ")[:100] if shape.has_text_frame else ""
        print(f"{shape.name}\t{shape.shape_type}\t{text}")


def generate(args: argparse.Namespace) -> None:
    template = args.template.resolve()
    output = args.output.resolve()
    if template.suffix.lower() != ".pptx" or not template.is_file():
        raise ValueError(f"Template must be an existing .pptx: {template}")
    if output == template:
        raise ValueError("Output must not overwrite the source template")
    if output.exists() and not args.force:
        raise ValueError(f"Output already exists; use --force to replace it: {output}")

    content = read_json(args.content)
    languages = bilingual_content(content)
    mapping = {**TEXT_FIELDS, **IMAGE_FIELDS}
    if args.mapping:
        mapping.update({str(k): str(v) for k, v in read_json(args.mapping).items()})

    presentation = Presentation(template)
    if not 1 <= args.fr_slide <= len(presentation.slides):
        raise ValueError(f"French slide {args.fr_slide} does not exist")
    french_slide = presentation.slides[args.fr_slide - 1]
    if args.en_slide:
        if not 1 <= args.en_slide <= len(presentation.slides):
            raise ValueError(f"English slide {args.en_slide} does not exist")
        english_slide = presentation.slides[args.en_slide - 1]
    else:
        english_slide = clone_slide(presentation, french_slide)
    retain_slides(presentation, [french_slide, english_slide])
    unresolved = fill_screenshots(
        french_slide, content, args.content, mapping, IMAGE_FIELDS
    )
    fill_screenshots(english_slide, content, args.content, mapping, IMAGE_FIELDS)
    fill_slide(french_slide, languages["fr"], mapping, TEXT_FIELDS)
    fill_slide(english_slide, languages["en"], mapping, TEXT_FIELDS)

    output.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(output)
    check = Presentation(output)
    if len(check.slides) != 2:
        raise RuntimeError("Generated deck must contain exactly 2 slides")
    print(f"Generated: {output}")
    print("Slides: 1=FR, 2=EN")
    print("Unresolved screenshot placeholders: " + (", ".join(unresolved) or "none"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="List template shape names and text")
    inspect.add_argument("--template", type=Path, required=True)
    inspect.add_argument("--slide", type=int, default=1)
    create = commands.add_parser("generate", help="Generate an editable one-pager")
    create.add_argument("--template", type=Path, required=True)
    create.add_argument("--content", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--mapping", type=Path)
    create.add_argument("--fr-slide", type=int, default=1)
    create.add_argument("--en-slide", type=int, default=2)
    create.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "inspect":
            inspect_template(args.template.resolve(), args.slide)
        else:
            generate(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
