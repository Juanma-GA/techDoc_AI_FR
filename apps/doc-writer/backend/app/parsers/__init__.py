"""Parsers : extraction de texte brut depuis PDF / DOCX / PPTX / XLSX / TXT / MD.

Tous renvoient `{"text": str}` pour qu'un consommateur n'ait pas a se soucier
du format en aval (chunking, indexation).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.errors import AppError

from . import docx_parser, pdf_parser, pptx_parser, txt_parser, xlsx_parser


SUPPORTED_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".xlsm", ".txt", ".md"}


def parse_any(path: str, *, mistral=None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Dispatch par extension. Renvoie `{"text": str}`.

    `mistral` ne concerne que le PDF : si un client est fourni, l'OCR document
    Mistral est tente (repli local sinon). Les autres formats l'ignorent.
    """
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return pdf_parser.parse(path, mistral=mistral)
    if ext == ".docx":
        return docx_parser.parse(path)
    if ext == ".pptx":
        return pptx_parser.parse(path)
    if ext in {".xlsx", ".xlsm"}:
        return xlsx_parser.parse(path)
    if ext in {".txt", ".md"}:
        return txt_parser.parse(path)
    if ext == ".ppt":
        raise AppError(
            "UNSUPPORTED_FORMAT",
            "Le format binaire .ppt (Office 97-2003) n'est pas supporte. "
            "Convertis le fichier en .pptx avant import.",
            status_code=400,
            detail={"extension": ext, "supported": sorted(SUPPORTED_EXTS)},
        )
    raise AppError(
        "UNSUPPORTED_FORMAT",
        f"Format non supporté : {ext}",
        status_code=400,
        detail={"extension": ext, "supported": sorted(SUPPORTED_EXTS)},
    )
