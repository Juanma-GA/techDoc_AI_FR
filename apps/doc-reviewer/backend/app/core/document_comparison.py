"""Extract text and compare PDF lines while retaining page geometry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

import fitz

from app.core.errors import AppError

ChangeKind = Literal["added", "removed"]


@dataclass(frozen=True)
class PdfTextLine:
    text: str
    normalized: str
    page: int
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class ExtractedPdf:
    page_count: int
    lines: tuple[PdfTextLine, ...]


def extract_pdf_text(path: Path) -> ExtractedPdf:
    try:
        document = fitz.open(str(path))
    except (fitz.FileDataError, RuntimeError) as exc:
        raise AppError("PDF_INVALID", "Le PDF est illisible.", status_code=400) from exc

    try:
        lines: list[PdfTextLine] = []
        for page_number, page in enumerate(document, start=1):
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    text = "".join(span.get("text", "") or "" for span in line.get("spans", []))
                    normalized = re.sub(r"\s+", " ", text).strip()
                    if not normalized:
                        continue
                    raw_bbox = line.get("bbox", (0.0, 0.0, 0.0, 0.0))
                    bbox = tuple(float(value) for value in raw_bbox)
                    lines.append(
                        PdfTextLine(
                            text=text.strip(),
                            normalized=normalized,
                            page=page_number,
                            bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
                        )
                    )
        if not lines:
            raise AppError(
                "PDF_NO_TEXT_LAYER",
                "Aucun texte exploitable n'a été trouvé dans ce PDF. L'OCR n'est pas utilisé.",
                status_code=422,
            )
        return ExtractedPdf(page_count=document.page_count, lines=tuple(lines))
    finally:
        document.close()


def build_comparison_report(
    paths: list[Path],
    filenames: list[str],
    reference_index: int,
) -> dict[str, Any]:
    extracted = [extract_pdf_text(path) for path in paths]
    documents = [
        {"index": index, "filename": filenames[index], "page_count": item.page_count}
        for index, item in enumerate(extracted)
    ]
    comparisons: list[dict[str, Any]] = []
    reference = extracted[reference_index]
    for index, candidate in enumerate(extracted):
        if index == reference_index:
            continue
        changes = _diff_lines(reference.lines, candidate.lines)
        comparisons.append(
            {
                "document_index": index,
                "filename": filenames[index],
                "added_count": sum(change["kind"] == "added" for change in changes),
                "removed_count": sum(change["kind"] == "removed" for change in changes),
                "changes": changes,
            }
        )
    return {
        "reference_index": reference_index,
        "documents": documents,
        "comparisons": comparisons,
    }


def _diff_lines(
    reference: tuple[PdfTextLine, ...],
    candidate: tuple[PdfTextLine, ...],
) -> list[dict[str, Any]]:
    matcher = SequenceMatcher(
        a=[line.normalized for line in reference],
        b=[line.normalized for line in candidate],
    )
    changes: list[dict[str, Any]] = []
    for operation, ref_start, ref_end, candidate_start, candidate_end in matcher.get_opcodes():
        if operation in {"delete", "replace"}:
            changes.extend(_change("removed", line) for line in reference[ref_start:ref_end])
        if operation in {"insert", "replace"}:
            changes.extend(_change("added", line) for line in candidate[candidate_start:candidate_end])
    return changes


def _change(kind: ChangeKind, line: PdfTextLine) -> dict[str, Any]:
    return {
        "kind": kind,
        "page": line.page,
        "text": line.text,
        "bbox": list(line.bbox),
    }
