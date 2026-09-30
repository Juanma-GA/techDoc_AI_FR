"""Persistence helpers for validated, immutable compiled-rule versions."""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.core.compiled_rules import CompiledRule
from app.db.models import CompiledRuleVersion


def persist_compiled_rule(
    db: Session,
    rule: CompiledRule,
    *,
    source_ref: str | None = None,
    version: int = 1,
) -> CompiledRuleVersion:
    """Stage a validated compiled rule without committing the caller's transaction."""
    canonical_json = rule.model_dump_json(exclude_none=False)
    row = CompiledRuleVersion(
        code=rule.id,
        version=version,
        schema_version="1.0",
        source=rule.source,
        source_ref=source_ref or rule.origin_ref,
        compiled_json=canonical_json,
        content_sha256=hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
        active=rule.execution in {"deterministic", "semantic"},
        validation_error=rule.compilation_error,
    )
    db.add(row)
    db.flush()
    return row