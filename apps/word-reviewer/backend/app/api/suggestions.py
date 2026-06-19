"""Routes /api/v1/suggestions - statut + application des corrections.

- PATCH /{id}            : change le statut (accepted/rejected/edited/checked),
  le texte propose, ou une note de feedback.
- POST  /{id}/apply      : applique la correction dans le .docx -> nouvelle
  version + EditHistory (rollback-aware).
- POST  /{id}/apply-group: applique le meme remplacement a toutes les occurrences.

Seules les suggestions **localisees** (span texte concret : `char_end > char_start`)
sont applicables. Les detections structurelles / items manuels se cochent via PATCH.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import docx_editor
from app.core import docx_versioning as ver
from app.core.errors import AppError
from app.db.models import Document, EditHistory, Suggestion
from app.db.session import get_db
from app.schemas import SuggestionOut, SuggestionPatchIn


log = logging.getLogger("word_reviewer.suggestions")

router = APIRouter(prefix="/suggestions", tags=["suggestions"])

_ALLOWED_STATUS = {"open", "accepted", "rejected", "edited", "checked", "applied"}


def _get(db: Session, suggestion_id: uuid.UUID) -> Suggestion:
    sug = db.get(Suggestion, suggestion_id)
    if sug is None:
        raise AppError("NOT_FOUND", "Suggestion introuvable.", 404)
    return sug


def _is_applicable(sug: Suggestion) -> bool:
    return sug.char_end > sug.char_start and bool(sug.original_text)


@router.patch("/{suggestion_id}", response_model=SuggestionOut)
def patch_suggestion(
    suggestion_id: uuid.UUID, payload: SuggestionPatchIn, db: Session = Depends(get_db)
) -> SuggestionOut:
    sug = _get(db, suggestion_id)
    if payload.status is not None:
        if payload.status not in _ALLOWED_STATUS:
            raise AppError("BAD_STATUS", f"Statut invalide : {payload.status}.", 400)
        sug.status = payload.status
    if payload.proposed_text is not None:
        sug.proposed_text = payload.proposed_text
        if sug.status == "open":
            sug.status = "edited"
    if payload.feedback_note is not None:
        sug.feedback_note = payload.feedback_note
    db.commit()
    return SuggestionOut.model_validate(sug)


def _new_version(db: Session, doc: Document, sug: Suggestion, new_bytes: bytes) -> int:
    before = doc.current_version
    after = before + 1
    ver.write_version(doc.storage_dir, after, new_bytes)
    db.add(
        EditHistory(
            document_id=doc.id,
            suggestion_id=sug.id,
            version_before=before,
            version_after=after,
            snapshot_path=str(ver.version_path(doc.storage_dir, before)),
            diff_summary=json.dumps({"rule_code": sug.rule_code, "target_id": sug.target_id}),
        )
    )
    doc.current_version = after
    return after


@router.post("/{suggestion_id}/apply", response_model=SuggestionOut)
def apply_suggestion(suggestion_id: uuid.UUID, db: Session = Depends(get_db)) -> SuggestionOut:
    sug = _get(db, suggestion_id)
    if not _is_applicable(sug):
        raise AppError(
            "NOT_APPLICABLE",
            "Cette suggestion n'est pas applicable automatiquement (detection / item manuel).",
            400,
        )
    doc = db.get(Document, sug.document_id)
    if doc is None:
        raise AppError("NOT_FOUND", "Document introuvable.", 404)

    data = ver.read_version(doc.storage_dir, doc.current_version)
    new_bytes, changed = docx_editor.apply_to_target(
        data, sug.target_id, sug.original_text, sug.proposed_text, sug.span_index
    )
    if not changed:
        raise AppError("APPLY_FAILED", "Texte cible introuvable (deja corrige ?).", 409)

    after = _new_version(db, doc, sug, new_bytes)
    sug.status = "applied"
    sug.applied_at = datetime.now(timezone.utc)
    sug.applied_version = after
    db.commit()
    return SuggestionOut.model_validate(sug)


@router.post("/{suggestion_id}/undo", response_model=list[SuggestionOut])
def undo_suggestion(suggestion_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SuggestionOut]:
    """Annule la derniere modification appliquee (restaure la version anterieure).

    Annulation LIFO : on ne peut defaire que la modification la plus recente
    (celle qui a produit la version courante). Reouvre toutes les suggestions
    rattachees a cette version (apply-group compris).
    """
    sug = _get(db, suggestion_id)
    doc = db.get(Document, sug.document_id)
    if doc is None:
        raise AppError("NOT_FOUND", "Document introuvable.", 404)
    edit = db.scalars(
        select(EditHistory)
        .where(
            EditHistory.suggestion_id == suggestion_id,
            EditHistory.rolled_back.is_(False),
        )
        .order_by(EditHistory.version_after.desc())
    ).first()
    if edit is None:
        raise AppError("NOT_APPLIED", "Cette suggestion n'a pas de modification a annuler.", 409)
    if edit.version_after != doc.current_version:
        raise AppError(
            "NOT_LAST",
            "Annule d'abord la modification la plus recente de ce document.",
            409,
        )

    edit.rolled_back = True
    doc.current_version = edit.version_before
    # Reouvre toutes les suggestions appliquees sur la version annulee.
    reopened = list(
        db.scalars(
            select(Suggestion).where(
                Suggestion.document_id == doc.id,
                Suggestion.applied_version == edit.version_after,
            )
        )
    )
    for s in reopened:
        s.status = "open"
        s.applied_at = None
        s.applied_version = None
    if sug not in reopened:
        reopened.append(sug)
    db.commit()
    # Nettoie le fichier de version annulee (best-effort, hors transaction).
    try:
        ver.version_path(doc.storage_dir, edit.version_after).unlink(missing_ok=True)
    except OSError:
        pass
    return [SuggestionOut.model_validate(s) for s in reopened]


@router.post("/{suggestion_id}/apply-group", response_model=list[SuggestionOut])
def apply_group(suggestion_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SuggestionOut]:
    sug = _get(db, suggestion_id)
    if not _is_applicable(sug):
        raise AppError("NOT_APPLICABLE", "Suggestion non applicable en groupe.", 400)
    doc = db.get(Document, sug.document_id)
    if doc is None:
        raise AppError("NOT_FOUND", "Document introuvable.", 404)

    data = ver.read_version(doc.storage_dir, doc.current_version)
    new_bytes, count = docx_editor.apply_group(data, sug.original_text, sug.proposed_text)
    if count == 0:
        raise AppError("APPLY_FAILED", "Aucune occurrence trouvee.", 409)

    after = _new_version(db, doc, sug, new_bytes)
    now = datetime.now(timezone.utc)
    siblings = list(
        db.scalars(
            select(Suggestion).where(
                Suggestion.document_id == doc.id,
                Suggestion.original_text == sug.original_text,
                Suggestion.proposed_text == sug.proposed_text,
                Suggestion.rule_code == sug.rule_code,
                Suggestion.status.in_(["open", "accepted", "edited"]),
            )
        )
    )
    for s in siblings:
        s.status = "applied"
        s.applied_at = now
        s.applied_version = after
    db.commit()
    return [SuggestionOut.model_validate(s) for s in siblings]
