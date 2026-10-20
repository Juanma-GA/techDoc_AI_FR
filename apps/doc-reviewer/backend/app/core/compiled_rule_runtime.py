"""Shared runtime types and document geometry for compiled-rule modules."""

from __future__ import annotations

import re
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy.orm import Session

from app.core.compiled_rules import (
    DocxEvidenceLocation,
    Evidence,
    PdfEvidenceLocation,
    RuleTarget,
)
from app.parsers.docx_parser import Block
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, find_span_bbox

_ENTITY_PATTERNS = {
    "cmm_number": re.compile(r"(?<!\w)(\d{2}-\d{2}-\d{2})(?!\w)"),
    "thales_logo_t": re.compile(r"^\s*(T)\s*$"),
    "revision_number": re.compile(
        r"(?i)\b(?:rev(?:ision)?\s*(?:no\.?|number|n°)?\s*[:#-]?\s*)([^\n|]+)"
    ),
    "revision_date": re.compile(r"(?i)\brevision\s+date\s*[:#-]?\s*([^\n|]+)"),
    "first_issue_date": re.compile(r"(?i)\bfirst\s+issue\s+date\s*[:#-]?\s*([^\n|]+)"),
    "copyright_start_year": re.compile(r"(?i)(?:©|copyright)\s*(\d{4})"),
    "copyright_end_year": re.compile(r"(?i)(?:©|copyright)\s*\d{4}\s*[-–]\s*(\d{4})"),
}

_BBox = tuple[float, float, float, float]
_SpanRange = tuple[int, int, _BBox, float, str]
_DOCUMENT_METADATA_FIELDS = (
    "meta_revision_date",
    "meta_cmm_number",
    "meta_first_issue_date",
    "meta_last_issue_date",
    "meta_revision_number",
    "meta_pnr_number",
    "meta_manufacturer",
    "document_language",
)
_CONTEXT_TOKEN_RE = re.compile(r"\{\{(?:document\.)?([A-Za-z_][A-Za-z0-9_]*)\}\}")


@dataclass(frozen=True)
class _TextTarget:
    page: str
    text: str
    raw_page: int
    page_type: str | None = None
    page_modified: bool | None = None
    bbox: _BBox | None = None
    target_id: str | None = None
    span_ranges: tuple[_SpanRange, ...] = ()
    text_offset: int = 0


@dataclass(frozen=True)
class _EvalContext:
    """Runtime data needed by operators and suggestion generation."""

    all_targets: list[_TextTarget]
    is_docx: bool
    blocks: list[Block] | None
    pdf_pages: list[ParsedPage] | None
    document: Any | None
    db: Session | None
    client_operations: Mapping[str, Any] | None = None
    client_entities: Mapping[str, str] | None = None
    inconclusive_pages: dict[str, list[int]] = field(default_factory=dict)
    # Required by the operators whose verdict spans the whole document
    # (cross-page consistency); None on the docx pipeline.
    parsed_pdf: ParsedPdf | None = None
    previous_revision_pdf: ParsedPdf | None = None


def document_metadata(document: Any | None) -> dict[str, str]:
    if document is None:
        return {}
    metadata: dict[str, Any] = {}
    raw_metadata = getattr(document, "client_metadata", None)
    if isinstance(raw_metadata, Mapping):
        metadata.update(raw_metadata)
    for field in _DOCUMENT_METADATA_FIELDS:
        if field not in metadata:
            metadata[field] = getattr(document, field, None)
        pnr_numbers = metadata.get("meta_pnr_number")
        if isinstance(pnr_numbers, list):
            metadata["meta_first_pnr_number"] = next(
                (
                    str(value).strip()
                    for value in pnr_numbers
                    if value is not None and str(value).strip()
                ),
                None,
            )
        elif pnr_numbers is not None:
            metadata["meta_first_pnr_number"] = pnr_numbers
    return {
        field: rendered
        for field, value in metadata.items()
        if (rendered := _metadata_text(value))
    }


def _metadata_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return json.dumps(
            [str(item).strip() for item in value if str(item).strip()],
            ensure_ascii=False,
        )
    return str(value).strip()


def page_span_ranges(page: ParsedPage) -> tuple[_SpanRange, ...]:
    page_text = page.text or ""
    ranges: list[_SpanRange] = []
    cursor = 0
    for span in page.spans:
        span_text = span.text.strip()
        if not span_text:
            continue
        start = page_text.find(span_text, cursor)
        if start < 0:
            whitespace_pattern = r"\s+".join(
                re.escape(part) for part in span_text.split()
            )
            match = re.search(whitespace_pattern, page_text[cursor:])
            if match is None:
                continue
            start = cursor + match.start()
            end = cursor + match.end()
        else:
            end = start + len(span_text)
        ranges.append((start, end, span.bbox, float(span.size), str(span.font)))
        cursor = end
    return tuple(ranges)


def scope_targets(
    target_spec: RuleTarget,
    targets: list[_TextTarget],
    *,
    is_docx: bool,
    blocks: list[Block] | None,
    pdf_pages: list[ParsedPage] | None,
) -> list[_TextTarget] | None:
    scoped = targets if target_spec.page == "all" else [target for target in targets if target.page == target_spec.page]
    allowed_page_types = target_spec.page_types
    if target_spec.page_type is not None:
        allowed_page_types = [target_spec.page_type]
    if allowed_page_types is not None:
        scoped = [target for target in scoped if target.page_type in allowed_page_types]
    if target_spec.excluded_page_types is not None:
        scoped = [
            target
            for target in scoped
            if target.page_type not in target_spec.excluded_page_types
        ]
    if target_spec.page_state is not None:
        # `None` means "undecided": the document does not declare which pages
        # the revision touched, so the rule must keep its full coverage
        # instead of silently vanishing.
        expected = target_spec.page_state == "modified"
        scoped = [
            target
            for target in scoped
            if target.page_modified is None or target.page_modified is expected
        ]
    if target_spec.region == "full_page":
        return scoped
    if is_docx:
        if blocks is None:
            return None
        if target_spec.region == "page_without_footer":
            allowed_ids = {block.target_id for block in blocks if block.zone != "footer"}
        else:
            allowed_ids = {
                block.target_id
                for block in blocks
                if block.zone == target_spec.region
            }
        return [target for target in scoped if target.target_id in allowed_ids]
    if pdf_pages is None:
        return None
    pages_by_number = {page.page: page for page in pdf_pages}
    selected: list[_TextTarget] = []
    for target in scoped:
        page = pages_by_number.get(target.raw_page)
        if page is None or not page.spans:
            continue
        min_y = min(span.bbox[1] for span in page.spans)
        max_y = max(span.bbox[3] for span in page.spans)
        height = max_y - min_y
        if height <= 0:
            continue
        if target_spec.region == "page_without_footer":
            footer_top = (
                page.page_height * 0.9
                if page.page_height > 0
                else max_y - max(height * 0.1, 50.0)
            )
            spans = [span for span in page.spans if span.bbox[1] < footer_top]
        elif target_spec.region == "header":
            spans = [span for span in page.spans if span.bbox[1] <= min_y + height * 0.25]
        elif target_spec.region == "footer":
            footer_top = (
                page.page_height * 0.9
                if page.page_height > 0
                else max_y - max(height * 0.1, 50.0)
            )
            spans = [span for span in page.spans if span.bbox[1] >= footer_top]
        else:
            spans = [
                span
                for span in page.spans
                if span.bbox[1] > min_y + height * 0.25
                and span.bbox[3] < max_y - height * 0.25
            ]
        if target_spec.page_type == "TP1" and target_spec.region == "footer":
            spans.sort(
                key=lambda span: (
                    (span.bbox[1] + span.bbox[3]) / 2,
                    span.bbox[0],
                )
            )
        if spans:
            text_parts: list[str] = []
            span_ranges: list[_SpanRange] = []
            cursor = 0
            for span in spans:
                part = span.text.strip()
                if not part:
                    continue
                if text_parts:
                    cursor += 1
                start = cursor
                cursor += len(part)
                text_parts.append(part)
                span_ranges.append((start, cursor, span.bbox, float(span.size), str(span.font)))
            selected.append(replace(target, text=" ".join(text_parts), span_ranges=tuple(span_ranges)))
    return selected or None


def evidence(
    target: _TextTarget | None,
    observed: str | None,
    expected: str | None,
    is_docx: bool,
    pdf_pages: list[ParsedPage] | None,
) -> Evidence:
    if target is None:
        location = (
            DocxEvidenceLocation(target_id="document")
            if is_docx
            else PdfEvidenceLocation(bbox=(0.0, 0.0, 0.0, 0.0))
        )
        return Evidence(page="", location=location, observed_value=observed, expected_value=expected)
    if is_docx:
        location = DocxEvidenceLocation(target_id=target.target_id or str(target.raw_page))
    else:
        evidence_text = observed or target.text
        local_offset = target.text.find(evidence_text) if observed else 0
        span_start = target.text_offset + max(local_offset, 0)
        location = PdfEvidenceLocation(
            bbox=observed_bbox(target, evidence_text, pdf_pages, span_start=span_start)
        )
    return Evidence(page=target.page, location=location, observed_value=observed, expected_value=expected)


def observed_bbox(
    target: _TextTarget,
    observed: str,
    pdf_pages: list[ParsedPage] | None,
    *,
    span_start: int = 0,
) -> _BBox:
    span_end = span_start + len(observed)
    overlaps = [
        bbox
        for start, end, bbox, _size, _font in target.span_ranges
        if end > span_start and start < span_end
    ]
    if overlaps:
        return union_bboxes(overlaps)
    if target.bbox is not None:
        return target.bbox
    if pdf_pages is not None:
        page = next((page for page in pdf_pages if page.page == target.raw_page), None)
        if page is not None:
            bbox = find_span_bbox(page.spans, observed, span_start, span_end)
            if is_nonzero_bbox(bbox):
                return bbox
    return first_bbox(target)


def is_nonzero_bbox(bbox: _BBox) -> bool:
    return bbox[2] > bbox[0] and bbox[3] > bbox[1]


def suggestion_bbox(
    target: _TextTarget,
    original: str,
    pdf_pages: list[ParsedPage] | None,
    *,
    span_start: int = 0,
) -> _BBox:
    return observed_bbox(target, original or target.text, pdf_pages, span_start=span_start)


def first_bbox(target: _TextTarget) -> _BBox:
    if target.bbox is not None:
        return target.bbox
    if target.span_ranges:
        return target.span_ranges[0][2]
    return (0.0, 0.0, 0.0, 0.0)


def union_bboxes(bboxes: list[_BBox]) -> _BBox:
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )
