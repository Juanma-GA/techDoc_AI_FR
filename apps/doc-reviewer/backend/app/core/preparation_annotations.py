from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.pdf_versioning import current_path
from app.core.preparation_state import _load_json
from app.db.models import AnalysisRun, Document, Suggestion
from app.db.preparation_models import DocumentPreparation
from app.parsers.pdf_parser import parse_pdf


_TOC_RULE_PREFIX = "THALES_PREP_TOC_PAGE_"


def sync_toc_annotations(
    db: Session,
    document: Document,
    preparation: DocumentPreparation,
) -> list[str]:
    decisions = _load_json(preparation.page_decisions_json, "page_decisions_json")
    parsed = parse_pdf(current_path(document.storage_dir, document.current_version))
    page_by_number = {page.page: page for page in parsed.pages}
    latest_run = db.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.document_id == document.id, AnalysisRun.status == "done")
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    )
    db.execute(
        delete(Suggestion).where(
            Suggestion.document_id == document.id,
            Suggestion.rule_code.like(f"{_TOC_RULE_PREFIX}%"),
            Suggestion.status.notin_(("applied", "rejected")),
        )
    )
    created_codes: list[str] = []
    for decision in decisions:
        if decision.get("is_modified") is not True:
            continue
        page_number = int(decision["page"])
        target_page = page_by_number.get(page_number)
        if target_page is None:
            continue
        toc_page = decision.get("toc_page")
        toc_bbox = decision.get("toc_bbox")
        has_toc_location = (
            isinstance(toc_page, int)
            and isinstance(toc_bbox, list)
            and len(toc_bbox) == 4
            and int(toc_page) in page_by_number
        )
        annotation_page = int(toc_page) if has_toc_location else page_number
        annotation_bbox = (
            {
                "x0": float(toc_bbox[0]),
                "y0": float(toc_bbox[1]),
                "x1": float(toc_bbox[2]),
                "y1": float(toc_bbox[3]),
                "page_w": page_by_number[int(toc_page)].page_width,
                "page_h": page_by_number[int(toc_page)].page_height,
                "page_rotation": 0,
            }
            if has_toc_location and int(toc_page) in page_by_number
            else {}
        )
        rule_code = f"{_TOC_RULE_PREFIX}{page_number}"
        failures = decision.get("failures", [])
        reasons = "; ".join(
            str(item.get("message") or item.get("title") or item.get("rule_id") or "")
            for item in failures
            if isinstance(item, dict)
        )
        page_type = decision.get("page_type") or "type non déterminé"
        message = (
            f"Page PDF {page_number} ({page_type}) à modifier. "
            f"Contrôles en échec : {reasons or 'voir les suggestions de cette page'}."
        )
        if not has_toc_location:
            message += (
                " Entrée de table des matières non localisée de façon fiable ; "
                "ce point figure dans le résumé du PDF commenté."
            )
        db.add(
            Suggestion(
                document_id=document.id,
                run_id=latest_run.id if latest_run is not None else None,
                rule_kind="compiled_checklist",
                rule_code=rule_code,
                source_kind="checklist",
                severity="warning",
                message=message[:2000],
                original_text=str(decision.get("toc_entry") or ""),
                proposed_text="",
                page=annotation_page,
                bbox=json.dumps(annotation_bbox),
                span_index=0,
                status="open",
                feedback="",
                created_at=datetime.now(timezone.utc),
            )
        )
        created_codes.append(rule_code)
    db.commit()
    return created_codes
