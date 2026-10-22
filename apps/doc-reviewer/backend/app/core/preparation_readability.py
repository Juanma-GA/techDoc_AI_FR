from __future__ import annotations

from typing import Any

import fitz

from app.core.errors import AppError

READABILITY_VERSION = 1
MIN_NATIVE_TEXT_CHARS = 80


def native_text_is_usable(text: str) -> bool:
    normalized = " ".join(text.split())
    if len(normalized) < MIN_NATIVE_TEXT_CHARS:
        return False

    visible = [character for character in normalized if not character.isspace()]
    if not visible or any(not character.isprintable() for character in visible):
        return False
    if any(character == "\ufffd" for character in visible):
        return False

    alphanumeric = sum(character.isalnum() for character in visible)
    return alphanumeric >= 40 and alphanumeric / len(visible) >= 0.4


def analyze_pdf_pages(data: bytes) -> list[dict[str, Any]]:
    try:
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if pdf.page_count < 1:
                raise AppError(
                    "PREPARATION_DOCUMENT_INVALID",
                    "Le document ne contient aucune page.",
                    status_code=400,
                )
            pages = []
            for index, page in enumerate(pdf, start=1):
                text = page.get_text("text") or ""
                native_text_usable = native_text_is_usable(text)
                pages.append(
                    {
                        "page": index,
                        "native_text_chars": len(text.strip()),
                        "native_text_usable": native_text_usable,
                        "needs_ocr": not native_text_usable,
                        "readability_version": READABILITY_VERSION,
                        "width": float(page.rect.width),
                        "height": float(page.rect.height),
                    }
                )
            return pages
    except AppError:
        raise
    except (fitz.FileDataError, OSError, RuntimeError, ValueError) as exc:
        raise AppError(
            "PREPARATION_DOCUMENT_INVALID",
            "Le document PDF ne peut pas être lu pour la préparation.",
            status_code=400,
        ) from exc
