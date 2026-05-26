"""POST /api/v1/projects/{id}/analysis/run — exécute les contrôles FTM v4."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.checks.custom_rules import run_custom_rules
from app.checks.granule import run_granule
from app.checks.illustration import run_illustration
from app.checks.operations import run_operations
from app.checks.referentiel_items import run_referentiel_items
from app.checks.script import run_script
from app.checks.text_rules import run_text_rules
from app.core.errors import AppError
from app.core.indexer import index_file_version
from app.core.mistral_client import MistralClient, MistralError
from app.core.rules import ANOMALY_TYPES
from app.db.models import AnalysisRun, Anomaly, Project
from app.db.session import get_db
from app.parsers import parse_any
from app.schemas import AnalysisRunOut


router = APIRouter(tags=["analysis"])

# Pipeline de contrôle v4. Chaque check a la signature uniforme
# `run_X(db, project, run_id, mistral) -> list[Anomaly]`.
_CHECKS = (
    run_script,
    run_granule,
    run_text_rules,
    run_operations,
    run_referentiel_items,
    run_illustration,
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
def run_analysis(project_id: uuid.UUID, db: Session = Depends(get_db)) -> AnalysisRun:
    project = _project_or_404(db, project_id)

    run = AnalysisRun(project_id=project.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    mistral: MistralClient | None
    try:
        mistral = MistralClient.from_db(db)
    except MistralError:
        mistral = None

    try:
        # Re-parse les dernières versions pour rafraîchir `extracted_text` :
        # les checks consomment ce champ et ont besoin des marqueurs à jour
        # (`[ONGLET: …]`, `[PAGE: …]`) introduits par les parsers.
        for f in project.files:
            if not f.versions:
                continue
            latest = sorted(f.versions, key=lambda v: v.uploaded_at)[-1]
            try:
                parsed = parse_any(latest.storage_path)
                text = parsed.get("text", "") or ""
                # PDF/image scanné sans couche texte → OCR Mistral de secours.
                latest.extracted_text = _ocr_if_needed(latest.storage_path, text, mistral)
            except Exception:  # noqa: BLE001
                continue
        db.commit()

        # Exécution séquentielle des contrôles v4.
        produced: list[Anomaly] = []
        for check in _CHECKS:
            produced.extend(check(db, project, run.id, mistral))
            db.commit()

        summary: dict[str, object] = {t: 0 for t in ANOMALY_TYPES}
        summary.update(Counter(a.type for a in produced))

        # Indexation RAG pour le chatbot (best-effort, ignore les erreurs).
        indexed = 0
        if mistral is not None:
            for f in project.files:
                if not f.versions:
                    continue
                latest = sorted(f.versions, key=lambda v: v.uploaded_at)[-1]
                try:
                    indexed += index_file_version(db, latest, mistral)
                except Exception:  # noqa: BLE001
                    continue
        summary["indexed_chunks"] = indexed

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


@router.delete("/projects/{project_id}/analysis/reset", status_code=204)
def reset_analysis(project_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    _project_or_404(db, project_id)
    db.execute(delete(Anomaly).where(Anomaly.project_id == project_id))
    db.execute(delete(AnalysisRun).where(AnalysisRun.project_id == project_id))
    db.commit()
