"""Routes /api/v1/admin - stats globales + reset.

`reset/all` purge les documents et leurs donnees liees (cascade : suggestions,
runs, historique) ainsi que les lots. `reset/rules` purge les regles custom.
Sont preserves : `app_config` (cle Mistral) et les standards builtin.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Batch, Document, Rule, Standard, Suggestion
from app.db.session import get_db
from app.schemas import AdminResetOut, AdminStatsOut, DashboardOut, DashboardTopDoc


log = logging.getLogger("word_reviewer.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    return AdminStatsOut(
        documents=db.scalar(select(func.count(Document.id))) or 0,
        batches=db.scalar(select(func.count(Batch.id))) or 0,
        suggestions=db.scalar(select(func.count(Suggestion.id))) or 0,
        rules=db.scalar(select(func.count(Rule.id))) or 0,
        standards=db.scalar(select(func.count(Standard.id))) or 0,
    )


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)) -> DashboardOut:
    def _grouped(column) -> dict[str, int]:
        rows = db.execute(
            select(column, func.count(Suggestion.id)).group_by(column)
        ).all()
        return {str(k): int(v) for k, v in rows}

    top_rows = db.execute(
        select(Document.id, Document.original_filename, func.count(Suggestion.id))
        .join(Suggestion, Suggestion.document_id == Document.id)
        .where(Suggestion.status == "open")
        .group_by(Document.id, Document.original_filename)
        .order_by(func.count(Suggestion.id).desc())
        .limit(10)
    ).all()
    top = [
        DashboardTopDoc(id=doc_id, original_filename=name, open_count=int(cnt))
        for doc_id, name, cnt in top_rows
    ]

    # Distribution « par sujet » (colonne TOPIC de la checklist = Rule.category).
    # Suggestion ne porte pas le topic -> jointure sur la regle. Les suggestions
    # des regles standard builtin ont rule_id NULL (pas de Rule) -> bucket de repli.
    topic_rows = db.execute(
        select(Rule.category, func.count(Suggestion.id))
        .select_from(Suggestion)
        .outerjoin(Rule, Suggestion.rule_id == Rule.id)
        .group_by(Rule.category)
    ).all()
    by_topic: dict[str, int] = {}
    for cat, cnt in topic_rows:
        if cat is None:
            label = "Controles standard"
        else:
            label = cat.strip() or "Sans sujet"
        by_topic[label] = by_topic.get(label, 0) + int(cnt)

    return DashboardOut(
        documents=db.scalar(select(func.count(Document.id))) or 0,
        batches=db.scalar(select(func.count(Batch.id))) or 0,
        by_status=_grouped(Suggestion.status),
        by_severity=_grouped(Suggestion.severity),
        by_kind=_grouped(Suggestion.rule_kind),
        by_topic=by_topic,
        top_documents=top,
    )


@router.post("/reset/all", response_model=AdminResetOut)
def reset_all(db: Session = Depends(get_db)) -> AdminResetOut:
    docs = db.scalar(select(func.count(Document.id))) or 0
    batches = db.scalar(select(func.count(Batch.id))) or 0
    rules = db.scalar(select(func.count(Rule.id))) or 0
    db.execute(delete(Document))  # cascade -> suggestions, runs, edit_history
    db.execute(delete(Batch))
    db.execute(delete(Rule))  # regles custom ; standards builtin + AppConfig preserves
    db.commit()
    log.info("admin reset all: %d documents, %d batches, %d rules", docs, batches, rules)
    return AdminResetOut(scope="all", deleted={"documents": docs, "batches": batches, "rules": rules})


@router.post("/reset/{scope}", response_model=AdminResetOut)
def reset_scope(scope: str, db: Session = Depends(get_db)) -> AdminResetOut:
    if scope == "all":
        return reset_all(db)
    if scope == "rules":
        n = db.scalar(select(func.count(Rule.id))) or 0
        db.execute(delete(Rule))
        db.commit()
        return AdminResetOut(scope="rules", deleted={"rules": n})
    if scope == "documents":
        n = db.scalar(select(func.count(Document.id))) or 0
        db.execute(delete(Document))
        db.commit()
        return AdminResetOut(scope="documents", deleted={"documents": n})
    raise AppError("BAD_SCOPE", f"Scope de reset inconnu : {scope}.", 400)
