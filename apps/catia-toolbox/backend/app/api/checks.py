"""Routes /api/v1 - verifications configurables sur un import."""

from __future__ import annotations

import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import load_parsed_nodes
from app.core import checks_engine
from app.core.errors import AppError
from app.db.models import CheckResult, CheckRun, StructureImport
from app.db.session import get_db
from app.schemas import CheckIn, CheckResultOut, CheckRunOut


router = APIRouter(tags=["checks"])


@router.get("/checks/rules", response_model=list[str])
def available_rules() -> list[str]:
    return checks_engine.AVAILABLE_RULES


@router.post("/imports/{import_id}/check", response_model=CheckRunOut)
def run_check(import_id: uuid.UUID, body: CheckIn, db: Session = Depends(get_db)) -> CheckRun:
    if db.get(StructureImport, import_id) is None:
        raise AppError("IMPORT_NOT_FOUND", "Import introuvable.", status_code=404, detail={"id": str(import_id)})
    nodes, _ = load_parsed_nodes(db, import_id)
    config = body.model_dump()
    results = checks_engine.run_checks(nodes, config)
    summary = checks_engine.summarize(results)

    run = CheckRun(
        import_id=import_id,
        config_json=json.dumps(config, ensure_ascii=False),
        summary=json.dumps(summary, ensure_ascii=False),
    )
    db.add(run)
    db.flush()
    for r in results:
        db.add(
            CheckResult(
                run_id=run.id,
                rule=r["rule"],
                severity=r["severity"],
                rel_path=r["rel_path"][:1000],
                message=r["message"],
            )
        )
    db.commit()
    db.refresh(run)
    return run


@router.get("/imports/{import_id}/checks", response_model=list[CheckRunOut])
def list_check_runs(import_id: uuid.UUID, db: Session = Depends(get_db)) -> list[CheckRun]:
    return list(
        db.scalars(
            select(CheckRun).where(CheckRun.import_id == import_id).order_by(CheckRun.created_at.desc())
        )
    )


@router.get("/checks/{run_id}/results", response_model=list[CheckResultOut])
def list_results(
    run_id: uuid.UUID,
    rule: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CheckResult]:
    if db.get(CheckRun, run_id) is None:
        raise AppError("CHECK_NOT_FOUND", "Verification introuvable.", status_code=404, detail={"id": str(run_id)})
    stmt = select(CheckResult).where(CheckResult.run_id == run_id)
    if rule:
        stmt = stmt.where(CheckResult.rule == rule)
    if severity:
        stmt = stmt.where(CheckResult.severity == severity)
    return list(db.scalars(stmt.order_by(CheckResult.rule, CheckResult.rel_path)))


@router.get("/checks/{run_id}/export.csv")
def export_checks(run_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    run = db.get(CheckRun, run_id)
    if run is None:
        raise AppError("CHECK_NOT_FOUND", "Verification introuvable.", status_code=404, detail={"id": str(run_id)})
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["rule", "severity", "rel_path", "message"])
    for r in run.results:
        w.writerow([r.rule, r.severity, r.rel_path, (r.message or "").replace("\n", " ")])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=checks_{str(run_id)[:8]}.csv"},
    )
