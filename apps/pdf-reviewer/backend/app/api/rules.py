"""Rules CRUD — user-defined regex rules used during analyze."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.llm_suggester import suggest_rules_from_corpus
from app.core.pdf_versioning import current_path
from app.core.rules_engine import validate_rule_pattern
from app.db.models import Document, Rule, StandardVersion
from app.db.session import get_db
from app.parsers.pdf_parser import parse_pdf
from app.schemas import (
    RuleIn,
    RuleOut,
    RulePatchIn,
    RuleSuggestIn,
    RuleSuggestionItem,
    RuleSuggestOut,
)

logger = structlog.get_logger(__name__)


_SUGGEST_TEXT_BUDGET = 12_000  # total chars sent to Mistral
_SUGGEST_PER_DOC_BUDGET = 2_000  # per-document char cap
_SUGGEST_MAX_DOCS = 20  # never sample more than this


router = APIRouter(tags=["rules"])


@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    standard_version_id: Optional[uuid.UUID] = Query(default=None),
    include_transverse: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[Rule]:
    """List rules.

    - No filter → every rule.
    - `standard_version_id=<id>` → rules scoped to that version, plus
      transverse rules (no standard_version_id) when `include_transverse`.
    - `standard_version_id=<id>&include_transverse=false` → strictly scoped.
    """
    stmt = select(Rule)
    if standard_version_id is not None:
        if include_transverse:
            stmt = stmt.where(
                or_(
                    Rule.standard_version_id == standard_version_id,
                    Rule.standard_version_id.is_(None),
                )
            )
        else:
            stmt = stmt.where(Rule.standard_version_id == standard_version_id)
    return list(db.scalars(stmt.order_by(Rule.created_at.desc())))


def _validate_standard_version(sv_id: Optional[uuid.UUID], db: Session) -> None:
    if sv_id is None:
        return
    if db.get(StandardVersion, sv_id) is None:
        raise AppError(
            "STANDARD_VERSION_NOT_FOUND",
            "Version de norme introuvable",
            status_code=400,
        )


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(body: RuleIn, db: Session = Depends(get_db)) -> Rule:
    validate_rule_pattern(body.pattern)
    _validate_standard_version(body.standard_version_id, db)
    rule = Rule(
        name=body.name,
        kind=body.kind,
        pattern=body.pattern,
        replacement=body.replacement,
        severity=body.severity,
        message=body.message,
        enabled=body.enabled,
        standard_version_id=body.standard_version_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=RuleOut)
def patch_rule(rule_id: uuid.UUID, body: RulePatchIn, db: Session = Depends(get_db)) -> Rule:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise AppError("RULE_NOT_FOUND", "Règle introuvable", status_code=404)
    if body.pattern is not None:
        validate_rule_pattern(body.pattern)
        rule.pattern = body.pattern
    if body.standard_version_id is not None:
        _validate_standard_version(body.standard_version_id, db)
        rule.standard_version_id = body.standard_version_id
    for field in ("name", "kind", "replacement", "severity", "message", "enabled"):
        value = getattr(body, field)
        if value is not None:
            setattr(rule, field, value)
    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise AppError("RULE_NOT_FOUND", "Règle introuvable", status_code=404)
    db.delete(rule)
    db.commit()


@router.post("/rules/suggest", response_model=RuleSuggestOut)
def suggest_rules(
    body: RuleSuggestIn | None = None,
    db: Session = Depends(get_db),
) -> RuleSuggestOut:
    """Ask Mistral to propose new editorial rules from already-uploaded PDFs.

    `body.document_ids` restricts the corpus; empty / missing means every
    document with extractable text. `body.standard_version_id` tailors the
    prompt to a specific norm (injects the existing catalog so the LLM
    doesn't duplicate built-in rules; returned suggestions carry that
    `standard_version_id` so the UI can apply them scoped to the norm).
    Suggestions are returned in-memory — they are NOT persisted; the UI
    applies the user-selected ones via the regular `POST /rules` endpoint.
    """
    import json as _json

    from app.db.models import StandardVersion

    body = body or RuleSuggestIn()
    standard_context: dict | None = None
    if body.standard_version_id is not None:
        sv = db.get(StandardVersion, body.standard_version_id)
        if sv is None:
            raise AppError(
                "STANDARD_VERSION_NOT_FOUND",
                "Version de norme introuvable",
                status_code=400,
            )
        try:
            catalog = _json.loads(sv.catalog_json or "[]")
        except _json.JSONDecodeError:
            catalog = []
        standard_context = {
            "code": sv.standard.code,
            "label": sv.standard.label,
            "description": sv.standard.description,
            "version_label": sv.label,
            "catalog": catalog if isinstance(catalog, list) else [],
        }

    stmt = select(Document)
    if body.document_ids:
        stmt = stmt.where(Document.id.in_(body.document_ids))
    documents = list(db.scalars(stmt.order_by(Document.created_at.desc())))
    if not documents:
        raise AppError(
            "NO_DOCS_FOR_SUGGESTIONS",
            "Aucun document dans le périmètre — uploade d'abord des PDFs.",
            status_code=400,
        )

    samples: list[str] = []
    total_chars = 0
    docs_analyzed = 0
    for doc in documents[:_SUGGEST_MAX_DOCS]:
        try:
            pdf_path = current_path(doc.storage_dir, doc.current_version)
            parsed = parse_pdf(pdf_path)
        except Exception as exc:
            # A missing or unparseable snapshot must not sink the whole call.
            logger.warning(
                "rule_suggest_doc_skipped",
                document_id=str(doc.id),
                error=type(exc).__name__,
                message=str(exc),
            )
            continue
        text = (parsed.full_text or "").strip()
        if not text:
            continue
        snippet = text[:_SUGGEST_PER_DOC_BUDGET]
        samples.append(f"=== {doc.original_filename} ===\n{snippet}")
        total_chars += len(snippet)
        docs_analyzed += 1
        if total_chars >= _SUGGEST_TEXT_BUDGET:
            break

    if not samples:
        raise AppError(
            "NO_TEXT_FOR_SUGGESTIONS",
            "Les documents du périmètre n'ont pas de texte exploitable. "
            "Re-upload un PDF avec une couche texte.",
            status_code=400,
        )

    try:
        items = suggest_rules_from_corpus(db, samples, standard_context=standard_context)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            "RULE_SUGGEST_FAILED",
            f"Mistral a échoué : {type(exc).__name__}: {exc}",
            status_code=502,
        ) from exc

    sv_id = body.standard_version_id
    return RuleSuggestOut(
        suggestions=[
            RuleSuggestionItem(**{**item, "standard_version_id": sv_id})
            for item in items
        ],
        documents_analyzed=docs_analyzed,
    )
