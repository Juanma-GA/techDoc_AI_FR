"""Routes /api/v1/rules - regles custom (CRUD) + import checklist Excel.

L'import est en **mode remplacement** (« repartir de 0 ») : les regles custom
existantes sont purgees avant de charger la nouvelle checklist. Les standards
builtin (ATA100) ne sont jamais touches.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.checklist_classifier import classify_rules
from app.core.errors import AppError
from app.core.excel_rules import list_sheets, parse_checklist
from app.core.rules_engine import validate_rule_pattern
from app.db.models import Rule
from app.db.session import get_db
from app.schemas import RuleImportResult, RuleIn, RuleOut, SheetInspectOut


log = logging.getLogger("word_reviewer.rules")

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db)) -> list[RuleOut]:
    stmt = select(Rule).order_by(Rule.category, Rule.name)
    return [RuleOut.model_validate(r) for r in db.scalars(stmt)]


@router.post("", response_model=RuleOut)
def create_rule(payload: RuleIn, db: Session = Depends(get_db)) -> RuleOut:
    validate_rule_pattern(payload.pattern, payload.kind)
    rule = Rule(**payload.model_dump())
    db.add(rule)
    db.commit()
    return RuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: uuid.UUID, payload: RuleIn, db: Session = Depends(get_db)) -> RuleOut:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise AppError("NOT_FOUND", "Regle introuvable.", 404)
    validate_rule_pattern(payload.pattern, payload.kind)
    for key, value in payload.model_dump().items():
        setattr(rule, key, value)
    db.commit()
    return RuleOut.model_validate(rule)


@router.delete("/{rule_id}")
def delete_rule(rule_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, bool]:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise AppError("NOT_FOUND", "Regle introuvable.", 404)
    db.delete(rule)
    db.commit()
    return {"deleted": True}


@router.post("/inspect", response_model=SheetInspectOut)
async def inspect_checklist(file: UploadFile) -> SheetInspectOut:
    """Liste les onglets + en-tetes + apercu d'un .xlsx (pour piloter l'import)."""
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise AppError("BAD_FORMAT", "Fichier Excel (.xlsx) attendu.", 400)
    data = await file.read()
    try:
        sheets = list_sheets(data)
    except Exception as exc:  # noqa: BLE001
        raise AppError("BAD_EXCEL", "Fichier Excel illisible.", 400) from exc
    return SheetInspectOut(sheets=sheets)


@router.post("/import", response_model=RuleImportResult)
async def import_checklist(
    file: UploadFile,
    sheet: str | None = Form(default=None),
    header_row: int = Form(default=0),
    topic_col: int | None = Form(default=None),
    check_col: int | None = Form(default=None),
    context_cols: str = Form(default=""),
    db: Session = Depends(get_db),
) -> RuleImportResult:
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise AppError("BAD_FORMAT", "Fichier Excel (.xlsx) attendu.", 400)
    data = await file.read()
    mapping = None
    if check_col is not None:
        try:
            ctx = [int(c) for c in json.loads(context_cols)] if context_cols else []
        except (ValueError, TypeError):
            ctx = []
        mapping = {"header_row": header_row, "topic": topic_col, "check": check_col, "context": ctx}
    try:
        parsed = parse_checklist(data, sheet=sheet, mapping=mapping)
    except Exception as exc:  # noqa: BLE001
        log.warning("checklist parse failed: %s", name)
        raise AppError("BAD_EXCEL", "Checklist Excel illisible.", 400) from exc
    if not parsed:
        raise AppError("EMPTY_CHECKLIST", "Aucune regle detectee dans la checklist.", 400)

    # Affinage LLM de la classification (repli heuristique si Mistral absent/erreur).
    try:
        parsed, llm_used = await classify_rules(db, parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("classification LLM echouee, repli heuristique: %s", exc)
        llm_used = False

    replaced = db.scalar(select(func.count(Rule.id))) or 0
    db.execute(delete(Rule))  # mode remplacement : repartir de 0

    by_kind: dict[str, int] = {}
    for pr in parsed:
        db.add(
            Rule(
                name=pr.name,
                category=pr.category,
                kind=pr.kind,
                pattern=pr.pattern,
                replacement=pr.replacement,
                target_zone=pr.target_zone,
                severity=pr.severity,
                message=pr.message,
                enabled=True,
                validated=False,  # file de validation : le relecteur valide ensuite
            )
        )
        by_kind[pr.kind] = by_kind.get(pr.kind, 0) + 1
    db.commit()
    return RuleImportResult(
        imported=len(parsed), replaced_count=replaced, by_kind=by_kind, skipped=[], llm_used=llm_used
    )


@router.post("/validate-all", response_model=dict)
def validate_all(db: Session = Depends(get_db)) -> dict:
    """Valide en bloc toutes les regles custom en attente (validated=False)."""
    pending = list(db.scalars(select(Rule).where(Rule.validated.is_(False))))
    for rule in pending:
        rule.validated = True
    db.commit()
    return {"validated": len(pending)}
