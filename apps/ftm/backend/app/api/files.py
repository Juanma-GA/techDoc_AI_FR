"""POST/GET/DELETE /api/v1/projects/{project_id}/files + référentiel v4."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.core.rules import BUILTIN_COLUMN_NAMES, reference_columns_for
from app.core.security import read_and_validate, safe_storage_join
from app.core.versioning import sha256_of_bytes
from app.db.models import Anomaly, DocumentChunk, File as DBFile, FileVersion, Project
from app.db.session import get_db
from app.parsers import parse_any
from app.parsers.reference import sheet_columns, sheet_names
from app.schemas import (
    FileOut,
    ReferenceColumnDef,
    ReferenceMappingIn,
    ReferenceOut,
    SheetColumnOut,
    UploadResultOut,
)

# Nom de colonne de référence utilisable en placeholder `{nom}` : lettre puis
# lettres / chiffres / underscore.
_COLUMN_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


router = APIRouter(tags=["files"])


# L'utilisateur peut uploader n'importe quel type de fichier ; on bloque
# uniquement les extensions exécutables ou clairement dangereuses pour
# éviter qu'un binaire actif transite par le storage.
# Le check « types_fichiers_attendus » dans Paramètres applique une liste
# blanche projet-spécifique au moment de l'analyse (anomalie type=naming).
BLOCKED_DOC_EXTS = {
    ".exe", ".dll", ".so", ".dylib", ".msi", ".com", ".scr",
    ".cmd", ".vbs", ".vbe", ".js.exe", ".jar", ".app", ".apk", ".deb", ".rpm",
}


def _project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise AppError("PROJECT_NOT_FOUND", "Projet introuvable",
                       status_code=404, detail={"id": str(project_id)})
    return p


@router.get("/projects/{project_id}/files", response_model=list[FileOut])
def list_files(project_id: uuid.UUID, db: Session = Depends(get_db)) -> list[DBFile]:
    return list(_project_or_404(db, project_id).files)


@router.post("/projects/{project_id}/files", response_model=UploadResultOut)
def upload_files(
    project_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> UploadResultOut:
    project = _project_or_404(db, project_id)

    created: list[dict] = []
    for upload in files:
        try:
            raw, safe_name, ext = read_and_validate(
                upload,
                max_size=settings.max_upload_size_bytes,
                blocked_exts=BLOCKED_DOC_EXTS,
            )
        except Exception as exc:  # AppError-friendly: take .detail / .message if AppError
            msg = getattr(exc, "detail", None) or str(exc)
            created.append({"filename": upload.filename, "ok": False, "error": msg})
            continue

        digest = sha256_of_bytes(raw)

        existing_file: DBFile | None = None
        for f in project.files:
            if f.current_name == safe_name:
                existing_file = f
                break

        if existing_file is None:
            existing_file = DBFile(
                project_id=project.id,
                current_name=safe_name,
                mime_type=upload.content_type or "",
            )
            db.add(existing_file)
            db.flush()
        else:
            if existing_file.versions:
                latest = sorted(existing_file.versions, key=lambda v: v.uploaded_at)[-1]
                if latest.sha256 == digest:
                    created.append({"filename": safe_name, "ok": True, "skipped": "identique"})
                    continue

        storage_root = safe_storage_join(
            Path(settings.storage_dir), f"project_{project.id}", f"file_{existing_file.id}",
        )
        storage_root.mkdir(parents=True, exist_ok=True)
        stored = safe_storage_join(storage_root, f"{digest[:12]}_{safe_name}")
        stored.write_bytes(raw)

        try:
            parsed = parse_any(str(stored))
            extracted_text = parsed.get("text", "")
        except Exception as e:  # noqa: BLE001
            extracted_text = f"[Parser error: {e}]"

        # État courant uniquement : on purge anomalies + chunks rattachés aux
        # versions précédentes de ce fichier. Les AnalysisRun restent (audit
        # trail), mais l'utilisateur ne verra plus les anomalies périmées
        # dans la vue Rédacteur ou les KPIs.
        if existing_file.versions:
            previous_ids = [v.id for v in existing_file.versions]
            db.query(Anomaly).filter(
                Anomaly.file_version_id.in_(previous_ids)
            ).delete(synchronize_session=False)
            db.query(DocumentChunk).filter(
                DocumentChunk.file_version_id.in_(previous_ids)
            ).delete(synchronize_session=False)

        version = FileVersion(
            file_id=existing_file.id,
            filename=safe_name,
            storage_path=str(stored),
            sha256=digest,
            size=len(raw),
            extracted_text=extracted_text,
        )
        db.add(version)
        existing_file.current_name = safe_name
        created.append({"filename": safe_name, "ok": True, "sha256": digest, "size": len(raw)})

    db.commit()
    return UploadResultOut(uploaded=created)


@router.delete("/projects/{project_id}/files/{file_id}", status_code=204)
def delete_file(project_id: uuid.UUID, file_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    f = db.get(DBFile, file_id)
    if not f or f.project_id != project_id:
        raise AppError("FILE_NOT_FOUND", "Fichier introuvable", status_code=404,
                       detail={"id": str(file_id)})
    db.delete(f)
    db.commit()


# ---------------------------------------------------------------------------
# Référentiel v4 — classeur Excel unique (onglets ATM / BASL / LCC).
# ---------------------------------------------------------------------------


def _reference_out(project: Project) -> ReferenceOut:
    """`ReferenceOut` complet (chemin + onglets + registre de colonnes)."""
    path = project.reference_path or None
    return ReferenceOut(
        path=path,
        sheets=sheet_names(path) if path else [],
        columns=[ReferenceColumnDef(**c) for c in reference_columns_for(project)],
    )


@router.post("/projects/{project_id}/reference", response_model=ReferenceOut)
def upload_reference(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ReferenceOut:
    """Attache (ou remplace) le classeur référentiel du projet. Le mapping des
    colonnes de référence (onglet + colonne de chaque entrée) se règle ensuite
    via `PUT /reference/mapping` à partir des onglets renvoyés ici."""
    project = _project_or_404(db, project_id)
    raw, _safe_name, ext = read_and_validate(
        file,
        allowed_exts={".xlsx", ".xlsm"},
        max_size=settings.max_upload_size_bytes,
    )
    dest_dir = safe_storage_join(
        Path(settings.storage_dir), f"project_{project_id}", "reference"
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = safe_storage_join(dest_dir, f"referentiel{ext}")
    dest.write_bytes(raw)
    project.reference_path = str(dest)
    db.commit()
    return _reference_out(project)


@router.get("/projects/{project_id}/reference", response_model=ReferenceOut)
def get_reference(project_id: uuid.UUID, db: Session = Depends(get_db)) -> ReferenceOut:
    return _reference_out(_project_or_404(db, project_id))


@router.get(
    "/projects/{project_id}/reference/columns",
    response_model=list[SheetColumnOut],
)
def get_reference_sheet_columns(
    project_id: uuid.UUID,
    sheet: str = Query(..., description="Titre exact de l'onglet du référentiel"),
    db: Session = Depends(get_db),
) -> list[SheetColumnOut]:
    """Colonnes (lettre + en-tête) d'un onglet du référentiel — alimente les
    menus déroulants « Colonne » de l'éditeur de mapping."""
    project = _project_or_404(db, project_id)
    if not project.reference_path:
        return []
    return [SheetColumnOut(**c) for c in sheet_columns(project.reference_path, sheet)]


@router.put("/projects/{project_id}/reference/mapping", response_model=ReferenceOut)
def update_reference_mapping(
    project_id: uuid.UUID,
    body: ReferenceMappingIn,
    db: Session = Depends(get_db),
) -> ReferenceOut:
    """Enregistre le registre des colonnes de référence (onglet + colonne de
    chaque entrée). Les 3 colonnes builtin sont toujours conservées ; les
    colonnes ajoutées doivent porter un nom unique en `[A-Za-z][A-Za-z0-9_]*`
    — utilisable comme placeholder `{nom}` dans les règles personnalisées."""
    project = _project_or_404(db, project_id)
    incoming = {c.name.strip(): c for c in body.columns}

    registry: list[dict] = []
    builtin_sheets: set[str] = set()
    for name in BUILTIN_COLUMN_NAMES:
        c = incoming.get(name)
        sheet = c.sheet.strip() if c else ""
        column = c.column.strip() if c else ""
        registry.append({"name": name, "sheet": sheet, "column": column, "builtin": True})
        if sheet:
            builtin_sheets.add(sheet)
    # Le check granule aligne script / granule_* ligne a ligne -> meme onglet.
    if len(builtin_sheets) > 1:
        raise AppError(
            "REFERENCE_MAPPING_INVALID",
            "Les colonnes script et granule doivent etre sur le meme onglet "
            "(le check granule les aligne ligne a ligne).",
            status_code=400,
            detail={"sheets": sorted(builtin_sheets)},
        )

    seen: set[str] = set(BUILTIN_COLUMN_NAMES)
    for c in body.columns:
        name = c.name.strip()
        if not name or name in BUILTIN_COLUMN_NAMES:
            continue
        if not _COLUMN_NAME_RE.match(name):
            raise AppError(
                "REFERENCE_MAPPING_INVALID",
                f"Nom de colonne invalide : « {name} ». Lettres, chiffres et "
                "« _ » uniquement, en commencant par une lettre.",
                status_code=400, detail={"name": name},
            )
        if name in seen:
            raise AppError(
                "REFERENCE_MAPPING_INVALID",
                f"Nom de colonne en double : « {name} ».",
                status_code=400, detail={"name": name},
            )
        seen.add(name)
        registry.append({
            "name": name, "sheet": c.sheet.strip(),
            "column": c.column.strip(), "builtin": False,
        })

    project.reference_columns = json.dumps(registry, ensure_ascii=False)
    db.commit()
    return _reference_out(project)


@router.delete("/projects/{project_id}/reference", status_code=204)
def delete_reference(project_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    project = _project_or_404(db, project_id)
    project.reference_path = None
    db.commit()


@router.post("/projects/{project_id}/basl", response_model=ReferenceOut)
def upload_basl(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ReferenceOut:
    """Attache (ou remplace) le fichier BASL du projet. Les checks rechanges /
    outillages / infrastructure / en-tête cross-checkent contre ce fichier."""
    project = _project_or_404(db, project_id)
    raw, _safe_name, ext = read_and_validate(
        file,
        allowed_exts={".xlsx", ".xlsm"},
        max_size=settings.max_upload_size_bytes,
    )
    dest_dir = safe_storage_join(
        Path(settings.storage_dir), f"project_{project_id}", "reference"
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = safe_storage_join(dest_dir, f"basl{ext}")
    dest.write_bytes(raw)
    project.basl_path = str(dest)
    db.commit()
    return ReferenceOut(path=str(dest), sheets=sheet_names(str(dest)))


@router.get("/projects/{project_id}/basl", response_model=ReferenceOut)
def get_basl(project_id: uuid.UUID, db: Session = Depends(get_db)) -> ReferenceOut:
    project = _project_or_404(db, project_id)
    if not project.basl_path:
        return ReferenceOut(path=None, sheets=[])
    return ReferenceOut(path=project.basl_path, sheets=sheet_names(project.basl_path))


@router.delete("/projects/{project_id}/basl", status_code=204)
def delete_basl(project_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    project = _project_or_404(db, project_id)
    project.basl_path = None
    db.commit()
