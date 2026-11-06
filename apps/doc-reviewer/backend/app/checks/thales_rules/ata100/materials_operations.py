from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.checks.client_bundle import ClientOperation, OperationResult
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, Span

from . import revision_engine as revision

_SECTION_TITLE_RE = re.compile(
    r"(?i)^\s*(?:"
    r"LIST\s+OF\s+MATERIALS|MATERIALS|"
    r"LIST\s+OF\s+CONSUMABLES(?:\s*\(\s*CONT['\u2019]?D\.?\s*\))?|CONSUMABLES|"
    r"SPECIAL\s+TOOLS(?:\s+AND\s+(?:EQUIPMENT|TOOLING))?|"
    r"SPECIAL\s+EQUIPMENT(?:\s+AND\s+(?:TOOLING|TOOLS))?|"
    r"LIST\s+OF\s+EQUIPMENT|EQUIPMENT\s+LIST"
    r")\s*$"
)
_DESIGNATION_HEADERS = {
    "designation",
    "description",
    "material",
    "consumable",
    "tool",
    "item",
    "item description",
    "part name",
}
_CODE_HEADERS = {"code", "part no", "part number", "reference", "ref"}
_SUPPLIER_HEADER_RE = re.compile(r"(?i)^suppliers?\b")
_USE_HEADERS = {"use", "usage", "application"}
_NOTE_RE = re.compile(r"(?i)\bNOTE\b")
_COMMERCIAL_AVAILABILITY = "commercially available"
_UNSPECIFIED_CODE = "not specific"
_ROW_TOP_TOLERANCE = 4.0
_DESIGNATION_LINE_GAP = 16.0
_EXPECTED_NO_NOTE = "Aucun texte NOTE dans les tableaux de materiaux, consommables et equipements."
_EXPECTED_ROW_ALIGNMENT = (
    "Les cellules DESCRIPTION, CODE, SUPPLIERS et USE d'un article doivent commencer au meme niveau vertical."
)
_EXPECTED_DEFAULTS = (
    "CODE = not specific et SUPPLIERS = Commercially available lorsque le code n'est pas specifie."
)


@dataclass(frozen=True)
class _TableHeader:
    spans: tuple[Span, ...]
    bottom: float
    left: float
    right: float
    labels: Mapping[str, Span]


@dataclass(frozen=True)
class _MaterialsLayout:
    header: _TableHeader
    designation_center: float
    code_center: float
    supplier_center: float
    use_center: float | None

    @property
    def designation_code_boundary(self) -> float:
        return (self.designation_center + self.code_center) / 2

    @property
    def code_supplier_boundary(self) -> float:
        return (self.code_center + self.supplier_center) / 2

    @property
    def supplier_use_boundary(self) -> float:
        if self.use_center is None:
            return self.header.right + 1.0
        return (self.supplier_center + self.use_center) / 2


@dataclass(frozen=True)
class _RowBand:
    top: float
    bottom: float
    designation_spans: tuple[Span, ...]


def _normalize_header(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _section_title_rows(page: ParsedPage) -> list[list[Span]]:
    rows = revision.visual_rows(page.spans)
    return [
        row
        for row in rows
        if _SECTION_TITLE_RE.fullmatch(" ".join(" ".join(span.text.split()) for span in row))
    ]


def _header_category(value: str) -> str | None:
    normalized = _normalize_header(value)
    if normalized in _DESIGNATION_HEADERS:
        return "designation"
    if normalized in _CODE_HEADERS:
        return "code"
    if _SUPPLIER_HEADER_RE.match(normalized):
        return "supplier"
    if normalized in _USE_HEADERS:
        return "use"
    return None


def _table_header(page: ParsedPage) -> _TableHeader | None:
    rows = revision.visual_rows(page.spans)
    title_rows = _section_title_rows(page)
    if not title_rows:
        return None
    title_bottom = max(span.bbox[3] for row in title_rows for span in row)
    eligible_rows = [row for row in rows if min(span.bbox[1] for span in row) > title_bottom]

    for start in range(len(eligible_rows)):
        window_rows = eligible_rows[start : start + 4]
        category_spans: dict[str, Span] = {}
        for row in window_rows:
            for span in row:
                category = _header_category(span.text.strip())
                if category is not None:
                    category_spans.setdefault(category, span)
        if "designation" not in category_spans or len(category_spans) < 2:
            continue
        spans = tuple(category_spans.values())
        return _TableHeader(
            spans=spans,
            bottom=max(span.bbox[3] for span in spans),
            left=min(span.bbox[0] for span in spans),
            right=max(span.bbox[2] for span in spans),
            labels=category_spans,
        )
    return None


def _materials_layout(page: ParsedPage) -> _MaterialsLayout | None:
    header = _table_header(page)
    if header is None or not {"designation", "code", "supplier"} <= header.labels.keys():
        return None
    return _MaterialsLayout(
        header=header,
        designation_center=(header.labels["designation"].bbox[0] + header.labels["designation"].bbox[2]) / 2,
        code_center=(header.labels["code"].bbox[0] + header.labels["code"].bbox[2]) / 2,
        supplier_center=(header.labels["supplier"].bbox[0] + header.labels["supplier"].bbox[2]) / 2,
        use_center=(
            (header.labels["use"].bbox[0] + header.labels["use"].bbox[2]) / 2
            if "use" in header.labels
            else None
        ),
    )


def _document_pages(context: Any) -> tuple[ParsedPdf | None, tuple[ParsedPage, ...]]:
    runtime = getattr(context, "runtime", context)
    parsed_pdf = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed_pdf, ParsedPdf):
        return None, ()
    target_pages = {target.raw_page for target in getattr(context, "targets", ())}
    pages = parsed_pdf.full_document_pages or parsed_pdf.pages
    if target_pages:
        pages = [page for page in pages if page.page in target_pages]
    return parsed_pdf, tuple(pages)


def _table_note_findings(
    context: Any,
) -> tuple[list[OperationResult], int]:
    _parsed_pdf, pages = _document_pages(context)
    findings: list[OperationResult] = []
    checked = 0
    for page in pages:
        header = _table_header(page)
        if header is None:
            continue
        checked += 1
        for span in page.spans:
            if (
                span.bbox[1] < header.bottom
                or span.bbox[0] >= header.right
                or span.bbox[2] <= header.left
                or _NOTE_RE.search(span.text) is None
            ):
                continue
            findings.append(
                OperationResult(
                    status="FAIL",
                    observed=span.text,
                    expected=_EXPECTED_NO_NOTE,
                    message=(
                        "Une NOTE est presente dans un tableau de materiaux, consommables ou equipements."
                    ),
                    original=span.text,
                    page=page.page,
                    bbox=span.bbox,
                )
            )
    return findings, checked


def _row_bands(page: ParsedPage, layout: _MaterialsLayout) -> list[_RowBand]:
    descriptor_spans = sorted(
        (
            span
            for span in page.spans
            if (span.bbox[0] + span.bbox[2]) / 2 < layout.designation_code_boundary
            and span.bbox[1] > layout.header.bottom
            and span.text.strip()
        ),
        key=lambda span: (span.bbox[1], span.bbox[0]),
    )
    if not descriptor_spans:
        return []

    groups: list[list[Span]] = []
    for span in descriptor_spans:
        if groups and span.bbox[1] - min(item.bbox[1] for item in groups[-1]) <= _DESIGNATION_LINE_GAP:
            groups[-1].append(span)
        else:
            groups.append([span])

    page_bottom = page.page_height or max(span.bbox[3] for span in page.spans)
    bands: list[_RowBand] = []
    for index, group in enumerate(groups):
        top = min(span.bbox[1] for span in group)
        next_top = min(span.bbox[1] for span in groups[index + 1]) if index + 1 < len(groups) else page_bottom
        bands.append(
            _RowBand(
                top=max(layout.header.bottom, top - 10.0),
                bottom=max(top + 10.0, next_top - 10.0),
                designation_spans=tuple(group),
            )
        )
    return bands


def _row_cells(
    page: ParsedPage,
    layout: _MaterialsLayout,
    band: _RowBand,
) -> dict[str, list[Span]]:
    cells: dict[str, list[Span]] = {
        "designation": [],
        "code": [],
        "supplier": [],
        "use": [],
    }
    for span in page.spans:
        center_x = (span.bbox[0] + span.bbox[2]) / 2
        center_y = (span.bbox[1] + span.bbox[3]) / 2
        if span.bbox[1] <= layout.header.bottom or not band.top <= center_y < band.bottom:
            continue
        if center_x < layout.designation_code_boundary:
            cells["designation"].append(span)
        elif center_x < layout.code_supplier_boundary:
            cells["code"].append(span)
        elif center_x < layout.supplier_use_boundary:
            cells["supplier"].append(span)
        else:
            cells["use"].append(span)
    return cells


def _cell_bbox(
    layout: _MaterialsLayout,
    band: _RowBand,
    column: str,
) -> tuple[float, float, float, float]:
    if column == "code":
        left, right = layout.designation_code_boundary, layout.code_supplier_boundary
    else:
        left, right = layout.code_supplier_boundary, layout.supplier_use_boundary
    return left, band.top, right, band.bottom


def _cell_text(spans: list[Span]) -> str:
    return " ".join(
        " ".join(span.text.split())
        for span in sorted(spans, key=lambda span: (span.bbox[1], span.bbox[0]))
        if span.text.strip()
    )


def _materials_row_findings(
    context: Any,
    control: str,
) -> tuple[list[OperationResult], int]:
    _parsed_pdf, pages = _document_pages(context)
    findings: list[OperationResult] = []
    checked = 0
    for page in pages:
        layout = _materials_layout(page)
        if layout is None:
            continue
        for band in _row_bands(page, layout):
            cells = _row_cells(page, layout, band)
            if not cells["designation"]:
                continue
            checked += 1
            if control == "row_alignment":
                row_top = min(span.bbox[1] for span in cells["designation"])
                for column in ("code", "supplier", "use"):
                    if not cells[column]:
                        continue
                    cell_top = min(span.bbox[1] for span in cells[column])
                    if abs(cell_top - row_top) <= _ROW_TOP_TOLERANCE:
                        continue
                    spans = cells[column]
                    findings.append(
                        OperationResult(
                            status="FAIL",
                            observed=_cell_text(spans),
                            expected=_EXPECTED_ROW_ALIGNMENT,
                            message=(
                                f"La colonne {column.upper()} n'est pas alignee en "
                                "haut avec la designation de l'article."
                            ),
                            original=_cell_text(spans),
                            page=page.page,
                            bbox=_cell_bbox(layout, band, column),
                        )
                    )
                continue

            code_text = _cell_text(cells["code"])
            supplier_text = _cell_text(cells["supplier"])
            unspecified = not code_text.strip() or _UNSPECIFIED_CODE in _normalize_header(code_text)
            if not unspecified:
                continue
            if _UNSPECIFIED_CODE not in _normalize_header(code_text):
                findings.append(
                    OperationResult(
                        status="FAIL",
                        observed=code_text or "(vide)",
                        expected=_UNSPECIFIED_CODE,
                        message=(
                            "La colonne CODE doit contenir « not specific » si aucun code n'est renseigne."
                        ),
                        original=code_text,
                        proposed=_UNSPECIFIED_CODE,
                        page=page.page,
                        bbox=_cell_bbox(layout, band, "code"),
                    )
                )
            if _COMMERCIAL_AVAILABILITY not in _normalize_header(supplier_text):
                findings.append(
                    OperationResult(
                        status="FAIL",
                        observed=supplier_text or "(vide)",
                        expected="Commercially available",
                        message=(
                            "La colonne SUPPLIERS doit contenir « Commercially "
                            "available » si aucun code n'est specifie."
                        ),
                        original=supplier_text,
                        proposed="Commercially available",
                        page=page.page,
                        bbox=_cell_bbox(layout, band, "supplier"),
                    )
                )
    return findings, checked


def _materials_findings(
    context: Any,
    parameters: Mapping[str, Any],
) -> tuple[list[OperationResult], int, str]:
    control = parameters.get("control")
    if control == "no_notes_in_tables":
        findings, checked = _table_note_findings(context)
        return findings, checked, _EXPECTED_NO_NOTE
    if control in {"row_alignment", "code_supplier_defaults"}:
        findings, checked = _materials_row_findings(context, str(control))
        expected = _EXPECTED_ROW_ALIGNMENT if control == "row_alignment" else _EXPECTED_DEFAULTS
        return findings, checked, expected
    raise ValueError(f"unknown ATA100 materials control: {control}")


def _evaluate_materials(
    context: Any,
    parameters: Mapping[str, Any],
) -> OperationResult:
    findings, checked, expected = _materials_findings(context, parameters)
    if findings:
        return findings[0]
    if not checked:
        return OperationResult(status="INCONCLUSIVE", expected=expected)
    targets = getattr(context, "targets", ())
    return OperationResult(
        status="PASS",
        expected=expected,
        page=targets[-1].raw_page if targets else None,
    )


def _suggest_materials(
    context: Any,
    parameters: Mapping[str, Any],
) -> list[OperationResult]:
    findings, _checked, _expected = _materials_findings(context, parameters)
    return findings


MATERIALS_CHECKS = ClientOperation(
    name="ata100_materials",
    execute=_evaluate_materials,
    suggestions=_suggest_materials,
)
