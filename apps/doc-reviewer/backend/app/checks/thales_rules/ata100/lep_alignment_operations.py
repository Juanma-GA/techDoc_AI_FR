from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.checks.client_bundle import ClientOperation, OperationResult
from app.parsers.pdf_parser import ParsedPdf, Span

from . import revision_engine as revision

_LEP_PAGE_COLUMN_TOLERANCE = 8.0
_LEP_PAGE_COLUMN_EXPECTED = (
    "Les numeros de page de chaque colonne PAGE de la LEP doivent etre alignes verticalement a 8 pt pres."
)


def _joined(spans: list[Span]) -> str:
    return " ".join(" ".join(span.text.split()) for span in spans if span.text.strip())


def _bbox(spans: list[Span]) -> tuple[float, float, float, float]:
    return (
        min(span.bbox[0] for span in spans),
        min(span.bbox[1] for span in spans),
        max(span.bbox[2] for span in spans),
        max(span.bbox[3] for span in spans),
    )


def _lep_page_column_findings(
    context: Any,
) -> tuple[list[OperationResult], int]:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed_pdf, ParsedPdf):
        return [], 0

    targets = tuple(getattr(context, "targets", ()))
    target_pages = {target.raw_page for target in targets}
    pages = parsed_pdf.full_document_pages or parsed_pdf.pages
    findings: list[OperationResult] = []
    checked_columns = 0

    for page in pages:
        if target_pages and page.page not in target_pages:
            continue
        if not revision._is_lep_page(page):
            continue

        rows = revision.visual_rows(page.spans)
        header = revision._lep_header(rows)
        if header is None:
            continue
        header_index, anchors = header
        header_groups = len(anchors) // len(revision._LEP_HEADER_CELLS)
        page_width = max((span.bbox[2] for span in page.spans), default=0.0)

        for group_index in range(header_groups):
            offset = group_index * len(revision._LEP_HEADER_CELLS)
            subject_x, page_x, date_x = anchors[offset : offset + 3]
            subject_max = (subject_x + page_x) / 2
            page_max = (page_x + date_x) / 2
            next_group = offset + len(revision._LEP_HEADER_CELLS)
            right_bound = (
                anchors[next_group] - revision._COLUMN_TOLERANCE
                if next_group < len(anchors)
                else page_width + 1.0
            )
            page_cells: list[tuple[str, tuple[float, float, float, float]]] = []

            for row in rows[header_index + 1 :]:
                cells = [
                    span
                    for span in row
                    if subject_x - revision._COLUMN_TOLERANCE <= span.bbox[0] < right_bound
                ]
                page_column_cells = [span for span in cells if subject_max <= span.bbox[0] < page_max]
                if not page_column_cells:
                    continue
                subject_cells = [
                    span
                    for span in cells
                    if span.bbox[0] < subject_max
                    and abs(span.bbox[0] - subject_x) <= revision._SUBJECT_ANCHOR_TOLERANCE
                ]
                subject_ids = {id(span) for span in subject_cells}
                prefix_cells = [
                    span for span in cells if span.bbox[0] < subject_max and id(span) not in subject_ids
                ]
                page_key = revision.normalize_page_key(
                    " ".join(
                        part
                        for part in (
                            _joined(prefix_cells),
                            _joined(page_column_cells),
                        )
                        if part
                    )
                )
                if page_key is None:
                    continue
                page_cells.append((page_key, _bbox(page_column_cells)))

            if len(page_cells) < 2:
                continue
            checked_columns += 1
            for page_key, cell_bbox in page_cells:
                if abs(cell_bbox[0] - page_x) <= _LEP_PAGE_COLUMN_TOLERANCE:
                    continue
                findings.append(
                    OperationResult(
                        status="FAIL",
                        observed=page_key,
                        expected=_LEP_PAGE_COLUMN_EXPECTED,
                        message=(
                            f"La page « {page_key} » n'est pas alignee avec les "
                            "autres numeros de la colonne PAGE de la LEP."
                        ),
                        original=page_key,
                        page=page.page,
                        bbox=cell_bbox,
                    )
                )

    return findings, checked_columns


def _evaluate_lep_page_column_alignment(
    context: Any,
    _parameters: Mapping[str, Any],
) -> OperationResult:
    findings, checked = _lep_page_column_findings(context)
    if findings:
        return findings[0]
    if not checked:
        return OperationResult(
            status="INCONCLUSIVE",
            expected=_LEP_PAGE_COLUMN_EXPECTED,
        )
    targets = getattr(context, "targets", ())
    return OperationResult(
        status="PASS",
        expected=_LEP_PAGE_COLUMN_EXPECTED,
        page=targets[-1].raw_page if targets else None,
    )


def _suggest_lep_page_column_alignment(
    context: Any,
    _parameters: Mapping[str, Any],
) -> list[OperationResult]:
    findings, _checked = _lep_page_column_findings(context)
    return findings


LEP_PAGE_COLUMN_ALIGNMENT = ClientOperation(
    name="ata100_lep_page_column_alignment",
    execute=_evaluate_lep_page_column_alignment,
    suggestions=_suggest_lep_page_column_alignment,
)
