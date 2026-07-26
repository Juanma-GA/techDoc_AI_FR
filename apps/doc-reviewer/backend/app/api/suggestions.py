"""Suggestions API — list / patch / bulk-status / apply / revert."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.pdf_editor import PatchSpec, apply_patch
from app.core.pdf_versioning import bump_version, current_path, path_for
from app.db.models import Document, EditHistory, Suggestion
from app.db.session import get_db
from app.schemas import (
    SuggestionApplyOut,
    SuggestionBulkStatusIn,
    SuggestionBulkStatusOut,
    SuggestionGroupApplyOut,
    SuggestionOut,
    SuggestionPatchIn,
)


router = APIRouter(tags=["suggestions"])


_ALLOWED_STATUSES = {"open", "accepted", "edited", "rejected"}

# Statuses a suggestion can be in and still be a candidate for `apply`.
_APPLICABLE_STATUSES = ("open", "accepted", "edited")


def _assert_applicable(s: Suggestion) -> None:
    """Raise the right AppError if `s` cannot be applied to the PDF.

    Shared by single `apply` and grouped `apply-group` so both reject
    already-applied / rejected / detection-only suggestions identically.
    """
    if s.status == "applied":
        raise AppError(
            "SUGGESTION_ALREADY_APPLIED",
            "Cette suggestion a déjà été appliquée",
            status_code=409,
        )
    if s.status == "rejected":
        raise AppError(
            "SUGGESTION_REJECTED",
            "Impossible d'appliquer une suggestion rejetée",
            status_code=400,
        )
    # Detection-only suggestions (structural rules like field_required,
    # step_pattern, …) carry an empty `proposed_text` because there's
    # no verbatim replacement to make — the user must edit the source
    # document. Refuse `apply` early with a stable error code.
    if not s.proposed_text or s.proposed_text == s.original_text:
        raise AppError(
            "SUGGESTION_DETECTION_ONLY",
            "Cette suggestion est détection-only : pas de correction automatique applicable.",
            status_code=400,
        )


def _apply_one(db: Session, s: Suggestion, doc: Document):
    """Patch one suggestion into `doc`'s current PDF version.

    Bumps the version, rewrites the PDF, updates suggestion + document
    state, invalidates stale same-page siblings and records EditHistory.
    Does NOT commit — the caller owns the transaction so single and
    grouped applies share one code path. Returns the `apply_patch` result.
    """
    bbox_dict = json.loads(s.bbox or "{}")
    bbox = (
        float(bbox_dict.get("x0", 0.0)),
        float(bbox_dict.get("y0", 0.0)),
        float(bbox_dict.get("x1", 0.0)),
        float(bbox_dict.get("y1", 0.0)),
    )

    src = current_path(doc.storage_dir, doc.current_version)
    snap = bump_version(doc.storage_dir, doc.current_version)

    try:
        result = apply_patch(
            src,
            snap.snapshot_path,
            PatchSpec(
                page=s.page,
                bbox=bbox,
                original_text=s.original_text,
                proposed_text=s.proposed_text,
                span_index=s.span_index,
            ),
        )
    except AppError:
        # Roll back the snapshot file on failure to keep the disk clean.
        try:
            snap.snapshot_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    previous = doc.current_version
    doc.current_version = snap.new_version
    doc.status = "edited"
    s.status = "applied"
    now = datetime.now(timezone.utc)
    s.applied_at = now
    s.applied_version = snap.new_version

    # Invalidate stale open suggestions on the same page: any other
    # `open` / `edited` suggestion whose `original_text` is contained
    # in (or contains) the text we just rewrote no longer points to a
    # valid location in the PDF. Mark them rejected with a clear reason
    # rather than leaving them dangling for the user to puzzle over.
    edited_text = (s.original_text or "").strip()
    if edited_text:
        sibling_stmt = select(Suggestion).where(
            Suggestion.document_id == doc.id,
            Suggestion.page == s.page,
            Suggestion.id != s.id,
            Suggestion.status.in_(("open", "edited", "accepted")),
        )
        for sibling in db.scalars(sibling_stmt):
            other = (sibling.original_text or "").strip()
            if not other:
                continue
            # Overlap is symmetrical: stale if the just-edited text
            # contains the sibling, or vice-versa, AND they're not the
            # same text (an identical row would just be a duplicate).
            if (other in edited_text or edited_text in other) and other != edited_text:
                sibling.status = "rejected"
                sibling.message = (
                    f"Stale après édition de « {edited_text[:60]} » "
                    f"(règle {s.rule_code})"
                )

    db.add(
        EditHistory(
            document_id=doc.id,
            suggestion_id=s.id,
            version_before=previous,
            version_after=snap.new_version,
            snapshot_path=str(snap.snapshot_path),
            diff_summary=json.dumps(
                {
                    "page": s.page,
                    "original": s.original_text,
                    "proposed": s.proposed_text,
                    "rule_code": s.rule_code,
                }
            ),
        )
    )
    return result


@router.get("/suggestions", response_model=list[SuggestionOut])
def list_suggestions(
    document_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    rule_kind: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Suggestion]:
    stmt = select(Suggestion)
    if document_id:
        stmt = stmt.where(Suggestion.document_id == document_id)
    if status:
        stmt = stmt.where(Suggestion.status == status)
    if severity:
        stmt = stmt.where(Suggestion.severity == severity)
    if rule_kind:
        stmt = stmt.where(Suggestion.rule_kind == rule_kind)
    return list(db.scalars(stmt.order_by(Suggestion.page, Suggestion.created_at)))


@router.post("/suggestions/bulk-status", response_model=SuggestionBulkStatusOut)
def bulk_update_status(
    body: SuggestionBulkStatusIn,
    db: Session = Depends(get_db),
) -> SuggestionBulkStatusOut:
    if body.status not in _ALLOWED_STATUSES:
        raise AppError(
            "SUGGESTION_STATUS_INVALID",
            f"Statut invalide. Valeurs autorisées : {sorted(_ALLOWED_STATUSES)}",
            status_code=400,
            detail={"status": body.status},
        )
    if not body.ids:
        return SuggestionBulkStatusOut(updated=0, status=body.status)
    rows = list(db.scalars(select(Suggestion).where(Suggestion.id.in_(body.ids))))
    for s in rows:
        s.status = body.status
        if body.feedback is not None:
            s.feedback = body.feedback
    db.commit()
    return SuggestionBulkStatusOut(updated=len(rows), status=body.status)


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionOut)
def get_suggestion(suggestion_id: uuid.UUID, db: Session = Depends(get_db)) -> Suggestion:
    s = db.get(Suggestion, suggestion_id)
    if s is None:
        raise AppError("SUGGESTION_NOT_FOUND", "Suggestion introuvable", status_code=404)
    return s


@router.patch("/suggestions/{suggestion_id}", response_model=SuggestionOut)
def patch_suggestion(
    suggestion_id: uuid.UUID,
    body: SuggestionPatchIn,
    db: Session = Depends(get_db),
) -> Suggestion:
    s = db.get(Suggestion, suggestion_id)
    if s is None:
        raise AppError("SUGGESTION_NOT_FOUND", "Suggestion introuvable", status_code=404)
    if s.status == "applied":
        raise AppError(
            "SUGGESTION_ALREADY_APPLIED",
            "Cette suggestion a déjà été appliquée au PDF",
            status_code=409,
        )
    s.status = body.status
    if body.proposed_text is not None:
        s.proposed_text = body.proposed_text
    if body.feedback is not None:
        s.feedback = body.feedback
    db.commit()
    db.refresh(s)
    return s


@router.post("/suggestions/{suggestion_id}/apply", response_model=SuggestionApplyOut)
def apply_suggestion(suggestion_id: uuid.UUID, db: Session = Depends(get_db)) -> SuggestionApplyOut:
    s = db.get(Suggestion, suggestion_id)
    if s is None:
        raise AppError("SUGGESTION_NOT_FOUND", "Suggestion introuvable", status_code=404)
    _assert_applicable(s)

    doc = db.get(Document, s.document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    result = _apply_one(db, s, doc)
    db.commit()

    return SuggestionApplyOut(
        suggestion_id=s.id,
        document_id=doc.id,
        new_version=doc.current_version,
        snapshot_path=str(path_for(doc.storage_dir, doc.current_version)),
        font_used=result.font_used,
        fallback_used=result.fallback_used,
        length_delta=result.length_delta,
        font_size_used=result.font_size_used,
        wrapped=result.wrapped,
    )


@router.post("/suggestions/{suggestion_id}/apply-group", response_model=SuggestionGroupApplyOut)
def apply_suggestion_group(
    suggestion_id: uuid.UUID, db: Session = Depends(get_db)
) -> SuggestionGroupApplyOut:
    """Apply the same anomaly across every page where it was detected.

    The "group" is every suggestion in the same document carrying the
    exact same fix — identical `rule_code`, `original_text` and
    `proposed_text`. Each member is patched in page order within a single
    transaction. Members that fail (text not found) or that an earlier
    member invalidated as a stale sibling are skipped, not aborted.
    """
    s = db.get(Suggestion, suggestion_id)
    if s is None:
        raise AppError("SUGGESTION_NOT_FOUND", "Suggestion introuvable", status_code=404)
    _assert_applicable(s)

    doc = db.get(Document, s.document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    group_stmt = (
        select(Suggestion)
        .where(
            Suggestion.document_id == doc.id,
            Suggestion.rule_code == s.rule_code,
            Suggestion.original_text == s.original_text,
            Suggestion.proposed_text == s.proposed_text,
            Suggestion.status.in_(_APPLICABLE_STATUSES),
        )
        .order_by(Suggestion.page, Suggestion.span_index)
    )
    members = list(db.scalars(group_stmt))

    applied_ids: list[uuid.UUID] = []
    pages: list[int] = []
    skipped = 0
    for member in members:
        # An earlier member may have invalidated this one as a stale
        # same-page sibling — re-check before patching.
        if member.status not in _APPLICABLE_STATUSES:
            skipped += 1
            continue
        try:
            _apply_one(db, member, doc)
        except AppError:
            # PDF-level failure on one page (e.g. text not found): skip
            # it and keep going so the other pages still get fixed.
            skipped += 1
            continue
        applied_ids.append(member.id)
        pages.append(member.page)

    db.commit()

    return SuggestionGroupApplyOut(
        suggestion_id=s.id,
        document_id=doc.id,
        new_version=doc.current_version,
        applied_count=len(applied_ids),
        skipped_count=skipped,
        applied_ids=applied_ids,
        pages=sorted(set(pages)),
    )


@router.post("/suggestions/{suggestion_id}/revert", response_model=SuggestionApplyOut)
def revert_suggestion(suggestion_id: uuid.UUID, db: Session = Depends(get_db)) -> SuggestionApplyOut:
    s = db.get(Suggestion, suggestion_id)
    if s is None:
        raise AppError("SUGGESTION_NOT_FOUND", "Suggestion introuvable", status_code=404)
    if s.status != "applied" or s.applied_version is None:
        raise AppError(
            "SUGGESTION_NOT_APPLIED",
            "Cette suggestion n'est pas appliquée — rien à annuler",
            status_code=400,
        )

    doc = db.get(Document, s.document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    target_version = s.applied_version - 1
    if target_version < 0:
        raise AppError("VERSION_INVALID", "Aucune version antérieure", status_code=400)

    target = path_for(doc.storage_dir, target_version)
    if not target.is_file():
        raise AppError("PDF_VERSION_MISSING", "Snapshot antérieur absent", status_code=404)

    previous = doc.current_version

    # Reverting a non-final patch invalidates every patch applied on top
    # of it (their snapshots are gone from `current_version`'s lineage).
    # Reset every applied suggestion whose `applied_version >= s.applied_version`
    # back to `open` so they can be re-applied if the user wants.
    cascade = list(
        db.scalars(
            select(Suggestion).where(
                Suggestion.document_id == doc.id,
                Suggestion.status == "applied",
                Suggestion.applied_version >= s.applied_version,
            )
        )
    )
    for sug in cascade:
        sug.status = "open"
        sug.applied_at = None
        sug.applied_version = None

    doc.current_version = target_version

    # If no suggestion remains in `applied` state, the document is no
    # longer "edited" — bring it back to "analyzed" so the UI badge is
    # honest.
    still_applied = db.scalar(
        select(Suggestion)
        .where(Suggestion.document_id == doc.id, Suggestion.status == "applied")
        .limit(1)
    )
    if still_applied is None and doc.status == "edited":
        doc.status = "analyzed"

    db.add(
        EditHistory(
            document_id=doc.id,
            suggestion_id=s.id,
            version_before=previous,
            version_after=target_version,
            snapshot_path=str(target),
            diff_summary=json.dumps(
                {"action": "revert", "cascade_count": len(cascade)}
            ),
            rolled_back=True,
        )
    )
    db.commit()
    return SuggestionApplyOut(
        suggestion_id=s.id,
        document_id=doc.id,
        new_version=target_version,
        snapshot_path=str(target),
        font_used="",
        fallback_used=False,
        length_delta=0,
    )
