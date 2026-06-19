"""Orchestrateur du moteur de regles (pendant docx du pdf-reviewer).

`run_all()` :
  1. charge les catalogues builtin des `StandardVersion` selectionnees
     (`catalog_json`), en retirant les `disabled_rule_codes` ;
  2. charge les regles custom (`Rule`) scopees aux standards selectionnes ou
     transverses ;
  3. normalise tout en dicts et execute `checks.runner.run()` sur le `ParsedDocx`
     (les regles `llm_nl` sont traitees a part par `core.llm_checks`) ;
  4. deduplique.

`materialize()` convertit les `RawSuggestion` en lignes ORM `Suggestion`.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.checks import runner
from app.checks.raw import RawSuggestion
from app.core.errors import AppError
from app.db.models import AnalysisRun, Document, Rule, StandardVersion, Suggestion
from app.parsers.docx_parser import ParsedDocx


# Kinds dont le `pattern` est un regex compile par le moteur.
_REGEX_KINDS = {"regex_flag", "regex_replace", "step_pattern", "zone_field", "style_check"}


def validate_rule_pattern(pattern: str, kind: str = "regex_flag") -> None:
    """Leve AppError si `pattern` n'est pas un regex valide (pour les kinds regex)."""
    if not pattern or kind not in _REGEX_KINDS:
        return
    try:
        re.compile(pattern)
    except re.error as exc:
        raise AppError("BAD_PATTERN", f"Expression reguliere invalide : {exc}", 400) from exc


def _catalog_dicts(versions: list[StandardVersion]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sv in versions:
        try:
            entries = json.loads(sv.catalog_json or "[]")
            disabled = set(json.loads(sv.disabled_rule_codes or "[]"))
        except (ValueError, TypeError):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("code") in disabled:
                continue
            meta = entry.get("metadata") or {}
            out.append(
                {
                    **entry,
                    "rule_kind": "standard",
                    "target_zone": entry.get("target_zone") or meta.get("zone", ""),
                    "metadata": meta,
                }
            )
    return out


def _custom_dicts(db: Session, version_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    # Seules les regles activees ET validees participent a l'analyse.
    stmt = select(Rule).where(Rule.enabled.is_(True), Rule.validated.is_(True))
    if version_ids:
        stmt = stmt.where(
            or_(
                Rule.standard_version_id.in_(version_ids),
                Rule.standard_version_id.is_(None),
            )
        )
    else:
        stmt = stmt.where(Rule.standard_version_id.is_(None))
    out: list[dict[str, Any]] = []
    for rule in db.scalars(stmt):
        meta: dict[str, Any] = {}
        if rule.target_zone:
            meta["zone"] = rule.target_zone
        out.append(
            {
                "code": f"CUSTOM_{rule.id.hex[:8]}",
                "title": rule.name,
                "kind": rule.kind,
                "severity": rule.severity,
                "pattern": rule.pattern,
                "replacement": rule.replacement,
                "message": rule.message or rule.name,
                "target_zone": rule.target_zone,
                "metadata": meta,
                "rule_kind": "custom",
                "rule_id": rule.id,
            }
        )
    return out


def _dedupe(raws: list[RawSuggestion]) -> list[RawSuggestion]:
    seen: set[tuple] = set()
    out: list[RawSuggestion] = []
    for raw in raws:
        key = raw.dedupe_key()
        if key in seen:
            continue
        seen.add(key)
        out.append(raw)
    return out


def build_rules(
    db: Session, standard_versions: Optional[list[StandardVersion]] = None
) -> list[dict[str, Any]]:
    """Liste des regles normalisees (builtin + custom) pour l'analyse."""
    versions = standard_versions or []
    version_ids = [sv.id for sv in versions]
    return _catalog_dicts(versions) + _custom_dicts(db, version_ids)


def run_all(
    parsed: ParsedDocx,
    document: Document,
    db: Session,
    standard_versions: Optional[list[StandardVersion]] = None,
) -> list[RawSuggestion]:
    rules = build_rules(db, standard_versions)
    return _dedupe(runner.run(parsed, rules))


def dedupe(raws: list[RawSuggestion]) -> list[RawSuggestion]:
    return _dedupe(raws)


def materialize(
    db: Session,
    document: Document,
    run: Optional[AnalysisRun],
    raws: list[RawSuggestion],
) -> list[Suggestion]:
    """Cree les lignes ORM `Suggestion` a partir des suggestions brutes."""
    counters: dict[tuple[str, str], int] = {}
    rows: list[Suggestion] = []
    for raw in raws:
        key = (raw.target_id, raw.original)
        span_index = counters.get(key, 0)
        counters[key] = span_index + 1
        row = Suggestion(
            document_id=document.id,
            run_id=run.id if run else None,
            rule_id=raw.rule_id,
            rule_kind=raw.rule_kind,
            rule_code=raw.rule_code,
            severity=raw.severity,
            message=raw.message,
            original_text=raw.original,
            proposed_text=raw.proposed,
            target_id=raw.target_id,
            block_index=raw.block_index,
            zone=raw.zone,
            semantic_zone=raw.semantic_zone,
            char_start=raw.char_start,
            char_end=raw.char_end,
            span_index=span_index,
            confidence=raw.confidence,
            status="open",
        )
        db.add(row)
        rows.append(row)
    return rows
