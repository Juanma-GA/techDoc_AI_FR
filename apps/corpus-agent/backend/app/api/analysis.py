"""POST /api/v1/projects/{id}/analysis/run — exécute les contrôles FTM v4."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.checks.cross_reference import run_reference_cross_checks
from app.checks.custom_rules import (
    CUSTOM_RULE_PROMPT_VERSION,
    RuleEvaluationStats,
    run_custom_rules,
)
from app.core.errors import AppError
from app.core.indexer import index_file_version
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled, requires_llm
from app.core.rules import ANOMALY_TYPES
from app.db.models import AnalysisRun, Anomaly, File, FileVersion, Project
from app.db.session import get_db
from app.parsers import parse_any
from app.schemas import AnalysisRunIn, AnalysisRunOut

router = APIRouter(tags=["analysis"])
log = structlog.get_logger(__name__)

# Pipeline de contrôle : le check déterministe des références s'exécute quand
# des colonnes du référentiel/BASL sont mappées ; la checklist métier reste
# évaluée par l'IA. Les contrôles de références fonctionnent aussi LLM désactivé.
_CHECKS = (
    run_reference_cross_checks,
    run_custom_rules,
)


# En dessous de ce volume de texte extrait, on suppose un document scanné
# sans couche texte → on tente un OCR Mistral.
_OCR_MIN_TEXT = 40
_OCR_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


def _ocr_if_needed(storage_path: str, current_text: str, mistral) -> str:
    """OCR de secours : si le parsing classique n'a quasiment rien extrait
    d'un PDF/image, on tente l'OCR Mistral (`/v1/ocr`). Best-effort : toute
    erreur conserve le texte courant."""
    if mistral is None or len((current_text or "").strip()) >= _OCR_MIN_TEXT:
        return current_text
    ext = Path(storage_path).suffix.lower()
    if ext not in _OCR_EXTS:
        return current_text
    try:
        data = Path(storage_path).read_bytes()
        if ext == ".pdf":
            mime = "application/pdf"
        elif ext in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        else:
            mime = f"image/{ext.lstrip('.')}"
        ocr_text = mistral.ocr(data, mime_type=mime)
        return ocr_text or current_text
    except Exception:  # noqa: BLE001
        return current_text


def _project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise AppError("PROJECT_NOT_FOUND", "Projet introuvable",
                       status_code=404, detail={"id": str(project_id)})
    return p


@router.post("/projects/{project_id}/analysis/run", response_model=AnalysisRunOut)
@requires_llm("corpus-agent.analysis.run")
def run_analysis(
    project_id: uuid.UUID,
    body: AnalysisRunIn | None = None,
    db: Session = Depends(get_db),
) -> AnalysisRun:
    # Eager load files + versions en 2 requetes (au lieu de 1 + N) : le pipeline
    # parcourt project.files et accede a f.versions dans plusieurs boucles
    # (re-parse, chaque check, indexation RAG). Avec expire_on_commit=False, ces
    # collections restent chargees a travers les commits successifs -> plus de
    # N+1 sur le chargement des versions.
    project = db.scalars(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.files).selectinload(File.versions))
    ).first()
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Projet introuvable",
                       status_code=404, detail={"id": str(project_id)})

    run = AnalysisRun(project_id=project.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    # Échantillon optionnel : restreint l'analyse (re-parse, checks, indexation)
    # à un sous-ensemble de fichiers. Liste vide / absente = tout le projet.
    target_ids: set[uuid.UUID] | None = set(body.file_ids) if body and body.file_ids else None
    target_files = [
        f for f in project.files if target_ids is None or f.id in target_ids
    ]
    coverage = {
        "files_in_project": len(project.files),
        "files_selected": len(target_files),
        "files_without_version": 0,
        "files_parse_failed": 0,
        "files_parsed": 0,
        "files_with_text": 0,
        "files_empty": 0,
        "indexing_failures": 0,
    }
    processable_ids: set[uuid.UUID] = set()
    latest_by_file: dict[uuid.UUID, FileVersion] = {}

    # Interrupteur global IA : si OFF, on force `mistral = None`. La checklist
    # métier est alors ignorée ; les cross-checks déterministes référentiel/BASL
    # continuent de tourner. La clé Mistral reste préservée.
    mistral: MistralClient | None
    if not get_llm_enabled(db):
        mistral = None
    else:
        try:
            mistral = MistralClient.from_db(db)
        except MistralError:
            mistral = None

    try:
        # Re-parse les dernières versions pour rafraîchir `extracted_text` :
        # les checks consomment ce champ et ont besoin des marqueurs à jour
        # (`[ONGLET: …]`, `[PAGE: …]`) introduits par les parsers.
        for f in target_files:
            if not f.versions:
                coverage["files_without_version"] += 1
                continue
            latest = sorted(f.versions, key=lambda v: v.uploaded_at)[-1]
            latest_by_file[f.id] = latest
            try:
                parsed = parse_any(latest.storage_path)
                text = parsed.get("text", "") or ""
                # PDF/image scanné sans couche texte → OCR Mistral de secours.
                latest.extracted_text = _ocr_if_needed(latest.storage_path, text, mistral)
                coverage["files_parsed"] += 1
                if latest.extracted_text.strip():
                    coverage["files_with_text"] += 1
                    processable_ids.add(f.id)
                else:
                    coverage["files_empty"] += 1
            except Exception as exc:
                coverage["files_parse_failed"] += 1
                log.warning(
                    "analysis_file_parse_failed",
                    project_id=str(project.id),
                    file_id=str(f.id),
                    error_type=type(exc).__name__,
                )
                continue
        db.commit()

        # --- Memoire des rejets + purge anti-accumulation -------------------
        # Signature d'une anomalie : (sujet, passage verbatim ou message). Deux
        # analyses du meme ecart produisent la meme signature.
        def _sig(a: Anomaly) -> tuple[str, str]:
            return (
                (a.category or "").strip().lower(),
                (a.evidence or a.location or a.message or "").strip().lower(),
            )

        processable_version_ids = {
            latest_by_file[file_id].id for file_id in processable_ids
        }
        old_stmt = select(Anomaly).where(
            Anomaly.project_id == project.id,
            Anomaly.file_version_id.in_(processable_version_ids),
        )
        old_anomalies = list(db.scalars(old_stmt))

        # Exécution séquentielle des contrôles v4.
        produced: list[Anomaly] = []
        evaluation_stats = RuleEvaluationStats()
        for check in _CHECKS:
            produced.extend(
                check(
                    db,
                    project,
                    run.id,
                    mistral,
                    only_file_ids=processable_ids,
                    stats=evaluation_stats,
                )
            )
            db.commit()

        evaluated_version_ids = {
            latest_by_file[file_id].id
            for file_id in evaluation_stats.evaluated_file_ids
        }
        evaluated_old_anomalies = [
            anomaly for anomaly in old_anomalies
            if anomaly.file_version_id in evaluated_version_ids
        ]
        evaluated_old_ids = {anomaly.id for anomaly in evaluated_old_anomalies}
        evaluated_old_anomalies.extend(
            anomaly
            for anomaly in old_anomalies
            if anomaly.type == "reference_cross_check"
            and anomaly.id not in evaluated_old_ids
        )
        # Rejected signatures are retained only for documents successfully
        # evaluated in this run; unavailable checks must not erase old findings.
        rejected_sigs = {
            _sig(anomaly)
            for anomaly in evaluated_old_anomalies
            if anomaly.status == "rejected"
        }
        for anomaly in evaluated_old_anomalies:
            if anomaly.status != "rejected":
                db.delete(anomaly)
        db.commit()

        # Capitalisation des rejets : on retire les anomalies re-signalees
        # identiques a un ecart deja rejete (meme sujet + meme passage).
        suppressed = 0
        if rejected_sigs:
            kept: list[Anomaly] = []
            for a in produced:
                if _sig(a) in rejected_sigs:
                    db.delete(a)
                    suppressed += 1
                else:
                    kept.append(a)
            produced = kept
            db.commit()

        summary: dict[str, object] = {t: 0 for t in ANOMALY_TYPES}
        summary.update(Counter(a.type for a in produced))
        if suppressed:
            summary["suppressed_rejected"] = suppressed
        has_verified_files = evaluation_stats.files_evaluated > 0
        complete_coverage = (
            coverage["files_selected"] > 0
            and has_verified_files
            and evaluation_stats.files_evaluated == coverage["files_selected"]
            and evaluation_stats.evaluation_failures == 0
            and coverage["files_without_version"] == 0
            and coverage["files_parse_failed"] == 0
            and coverage["files_empty"] == 0
        )
        summary["llm_used"] = mistral is not None
        summary["active_rules"] = evaluation_stats.active_rules
        summary["rule_set_sha256"] = evaluation_stats.rule_set_sha256
        summary["prompt_version"] = CUSTOM_RULE_PROMPT_VERSION
        summary["llm_model"] = str(getattr(mistral, "chat_model", "")) if mistral else ""
        summary["files_in_project"] = coverage["files_in_project"]
        summary["files_selected"] = coverage["files_selected"]
        summary["files_without_version"] = coverage["files_without_version"]
        summary["files_parse_failed"] = coverage["files_parse_failed"]
        summary["files_parsed"] = coverage["files_parsed"]
        summary["files_with_text"] = coverage["files_with_text"]
        summary["files_empty"] = coverage["files_empty"]
        summary["files_verified"] = evaluation_stats.files_evaluated
        summary["evaluation_calls"] = evaluation_stats.evaluation_calls
        summary["evaluation_failures"] = evaluation_stats.evaluation_failures
        summary["rules_evaluated"] = evaluation_stats.rules_evaluated
        summary["verification_status"] = (
            "verified" if complete_coverage else "partial" if has_verified_files else "not_verified"
        )

        # Indexation RAG pour le chatbot (best-effort, ignore les erreurs).
        indexed = 0
        if mistral is not None:
            for f in target_files:
                if f.id not in processable_ids or not f.versions:
                    continue
                latest = sorted(f.versions, key=lambda v: v.uploaded_at)[-1]
                try:
                    indexed += index_file_version(db, latest, mistral)
                except Exception as exc:
                    coverage["indexing_failures"] += 1
                    log.warning(
                        "analysis_file_index_failed",
                        project_id=str(project.id),
                        file_id=str(f.id),
                        error_type=type(exc).__name__,
                    )
                    continue
        summary["indexed_chunks"] = indexed
        summary["indexing_failures"] = coverage["indexing_failures"]

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.summary = json.dumps(summary, ensure_ascii=False, default=str)
        db.commit()
        db.refresh(run)
        return run
    except Exception as e:  # noqa: BLE001
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.summary = json.dumps({"error": str(e)})
        db.commit()
        raise AppError("ANALYSIS_FAILED", f"Analyse échouée : {e}", status_code=500) from e


@router.get("/projects/{project_id}/analysis/runs", response_model=list[AnalysisRunOut])
def list_runs(project_id: uuid.UUID, db: Session = Depends(get_db)) -> list[AnalysisRun]:
    return list(
        db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.project_id == project_id)
            .order_by(AnalysisRun.started_at.desc())
        )
    )


@router.delete("/projects/{project_id}/analysis/reset", status_code=204, response_class=Response)
def reset_analysis(project_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    _project_or_404(db, project_id)
    db.execute(delete(Anomaly).where(Anomaly.project_id == project_id))
    db.execute(delete(AnalysisRun).where(AnalysisRun.project_id == project_id))
    db.commit()
    return Response(status_code=204)
