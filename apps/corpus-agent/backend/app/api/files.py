"""POST/GET/DELETE /api/v1/projects/{project_id}/files + référentiel v4."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.core.rules import (
    BASL_BUILTIN_COLUMN_NAMES,
    BUILTIN_COLUMN_NAMES,
    basl_columns_for,
    reference_columns_for,
)
from app.core.security import (
    read_and_validate,
    safe_filename,
    safe_storage_join,
    validate_upload_bytes,
)
from app.core.versioning import sha256_of_bytes
from app.db.models import Anomaly, DocumentChunk, File as DBFile, FileVersion, Project
from app.db.session import get_db
from app.parsers import parse_any
from app.parsers.reference import sheet_columns, sheet_names, sheet_preview
from app.schemas import (
    CorpusFolderIn,
    CorpusPathOut,
    FileOut,
    FolderFileOut,
    FolderListOut,
    ReferenceColumnDef,
    ReferenceMappingIn,
    ReferenceOut,
    SheetColumnOut,
    SheetPreviewOut,
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


def _ingest_file(
    db: Session, project: Project, raw: bytes, safe_name: str, mime: str,
    rel_path: str | None = None,
) -> dict:
    """Ingère un fichier déjà lu + validé (bytes) : dédup par nom+hash, stockage
    sur disque, extraction texte, nouvelle `FileVersion`. Logique partagée entre
    l'upload manuel HTTP et la synchro d'un dossier connecté. NE COMMIT PAS
    (l'appelant groupe les commits). Renvoie un dict de résultat par fichier.

    `rel_path` (chemin relatif au dossier connecté, fourni uniquement par
    `sync_corpus_folder`) est la clé d'identité quand il est présent : deux
    fichiers de même nom dans des sous-dossiers différents (ex.
    `a/doc.txt` et `b/doc.txt`) restent alors des `File` distincts, plutôt que
    de collisionner sur `current_name` seul (bug corrigé : une re-synchro
    mélangeait silencieusement leurs historiques de versions). Un upload
    manuel (`rel_path=None`) garde l'ancienne identité par nom, au sein des
    seuls fichiers eux-mêmes sans `rel_path` (jamais confondu avec un fichier
    de dossier connecté)."""
    digest = sha256_of_bytes(raw)

    existing_file: DBFile | None = None
    for f in project.files:
        if rel_path is not None:
            if f.rel_path == rel_path:
                existing_file = f
                break
        elif f.rel_path is None and f.current_name == safe_name:
            existing_file = f
            break

    if existing_file is None:
        existing_file = DBFile(
            project_id=project.id,
            current_name=safe_name,
            rel_path=rel_path,
            mime_type=mime or "",
        )
        db.add(existing_file)
        db.flush()
    else:
        if existing_file.versions:
            latest = sorted(existing_file.versions, key=lambda v: v.uploaded_at)[-1]
            if latest.sha256 == digest:
                # Code stable (pas de prose FR en dur) : le frontend le
                # traduit via i18n (`files.skippedUnchanged`).
                return {"filename": safe_name, "ok": True, "skipped": "unchanged"}

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
    return {"filename": safe_name, "ok": True, "sha256": digest, "size": len(raw)}


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

        try:
            created.append(
                _ingest_file(db, project, raw, safe_name, upload.content_type or "")
            )
        except Exception as exc:  # noqa: BLE001 — un fichier KO n'annule pas le lot
            msg = getattr(exc, "detail", None) or str(exc)
            created.append({"filename": safe_name, "ok": False, "error": msg})

    db.commit()
    return UploadResultOut(uploaded=created)


@router.delete("/projects/{project_id}/files/{file_id}", status_code=204, response_class=Response)
def delete_file(project_id: uuid.UUID, file_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    f = db.get(DBFile, file_id)
    if not f or f.project_id != project_id:
        raise AppError("FILE_NOT_FOUND", "Fichier introuvable", status_code=404,
                       detail={"id": str(file_id)})
    db.delete(f)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Corpus par dossier connecté (chemin local, ex. dossier OneDrive synchronisé).
# Alternative à l'upload manuel : on pointe un dossier déjà synchronisé sur le
# disque et on ingère ses fichiers via la même logique (`_ingest_file`).
# ---------------------------------------------------------------------------

# Garde-fou : plafond de fichiers parcourus/ingérés en une passe (évite
# d'aspirer par erreur un arbre géant). Au-delà, on tronque et on le signale.
_FOLDER_MAX_FILES = 500


def _resolve_folder(raw_path: str) -> Path:
    """Valide un chemin de dossier fourni par l'utilisateur (guillemets tolérés)."""
    cleaned = (raw_path or "").strip().strip('"')
    if not cleaned:
        raise AppError("CORPUS_PATH_EMPTY", "Chemin de dossier vide.", status_code=400)
    folder = Path(cleaned)
    if not folder.exists() or not folder.is_dir():
        raise AppError(
            "CORPUS_PATH_INVALID",
            f"Dossier introuvable ou inaccessible : {cleaned}",
            status_code=400,
            detail={"path": cleaned},
        )
    return folder


def _walk_folder(folder: Path) -> tuple[list[tuple[Path, str]], bool]:
    """Fichiers du dossier (récursif), plafonnés. Renvoie (liste de (chemin,
    rel), tronqué?). `rel` = chemin relatif au dossier (identifiant stable pour
    la sélection côté UI)."""
    out: list[tuple[Path, str]] = []
    truncated = False
    for entry in folder.rglob("*"):
        if not entry.is_file():
            continue
        if len(out) >= _FOLDER_MAX_FILES:
            truncated = True
            break
        rel = entry.relative_to(folder).as_posix()
        out.append((entry, rel))
    return out, truncated


@router.get("/projects/{project_id}/corpus-folder", response_model=CorpusPathOut)
def get_corpus_folder(project_id: uuid.UUID, db: Session = Depends(get_db)) -> CorpusPathOut:
    return CorpusPathOut(path=_project_or_404(db, project_id).corpus_path or None)


@router.delete("/projects/{project_id}/corpus-folder", status_code=204, response_class=Response)
def disconnect_corpus_folder(project_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Oublie le dossier connecté (n'efface pas les fichiers déjà ingérés)."""
    project = _project_or_404(db, project_id)
    project.corpus_path = None
    db.commit()
    return Response(status_code=204)


@router.post("/projects/{project_id}/files/list-folder", response_model=FolderListOut)
def list_corpus_folder(
    project_id: uuid.UUID,
    body: CorpusFolderIn,
    db: Session = Depends(get_db),
) -> FolderListOut:
    """Liste (sans ingérer) les fichiers d'un dossier local pour permettre la
    sélection avant import. Les extensions bloquées sont incluses mais marquées
    `blocked=true` (affichées grisées côté UI)."""
    _project_or_404(db, project_id)
    folder = _resolve_folder(body.path)
    walked, truncated = _walk_folder(folder)
    files = [
        FolderFileOut(
            rel=rel,
            name=entry.name,
            size=entry.stat().st_size if entry.exists() else 0,
            ext=entry.suffix.lower(),
            blocked=entry.suffix.lower() in BLOCKED_DOC_EXTS,
        )
        for entry, rel in walked
    ]
    return FolderListOut(path=str(folder), files=files, truncated=truncated)


@router.post("/projects/{project_id}/files/sync-folder", response_model=UploadResultOut)
def sync_corpus_folder(
    project_id: uuid.UUID,
    body: CorpusFolderIn,
    db: Session = Depends(get_db),
) -> UploadResultOut:
    """Ingère les fichiers d'un dossier local (typiquement un dossier OneDrive
    synchronisé) via la même logique que l'upload manuel : parcours récursif,
    extensions bloquées ignorées, dédup par nom+hash. `body.only` (chemins
    relatifs) restreint à une sélection ; absent = tout le dossier. Mémorise le
    chemin dans `project.corpus_path`. Un fichier en échec (cloud-only non
    hydraté, illisible, trop volumineux) n'interrompt pas le lot."""
    project = _project_or_404(db, project_id)
    folder = _resolve_folder(body.path)
    only = {r.strip() for r in body.only if r and r.strip()} if body.only is not None else None

    walked, truncated = _walk_folder(folder)
    created: list[dict] = []
    for entry, rel in walked:
        if only is not None and rel not in only:
            continue
        safe_name = safe_filename(entry.name)
        ext = entry.suffix.lower()
        if ext in BLOCKED_DOC_EXTS:
            continue
        try:
            raw = entry.read_bytes()
            validate_upload_bytes(
                raw, ext, None, settings.max_upload_size_bytes, blocked_exts=BLOCKED_DOC_EXTS,
            )
            created.append(_ingest_file(db, project, raw, safe_name, "", rel_path=rel))
        except Exception as exc:  # noqa: BLE001 — un fichier KO n'annule pas le lot
            msg = getattr(exc, "detail", None) or str(exc)
            created.append({"filename": safe_name, "ok": False, "error": msg})

    project.corpus_path = str(folder)
    db.commit()

    if truncated:
        created.append({
            "filename": "", "ok": False,
            "error": f"Limite de {_FOLDER_MAX_FILES} fichiers atteinte — dossier tronque.",
        })
    return UploadResultOut(uploaded=created)


# ---------------------------------------------------------------------------
# Référentiel v4 — classeur Excel unique (onglets ATM / BASL / LCC).
# ---------------------------------------------------------------------------


def _header_rows(project: Project) -> dict[str, int]:
    """Map {onglet: ligne(1-based)} des lignes d'en-tête choisies. `{}` si non
    renseigné ou JSON corrompu (→ détection auto côté parser)."""
    try:
        data = json.loads(project.reference_header_rows or "{}")
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in data.items():
        try:
            n = int(v)
        except (ValueError, TypeError):
            continue
        if n >= 1:
            out[str(k)] = n
    return out


def _reference_out(project: Project) -> ReferenceOut:
    """`ReferenceOut` complet (chemin + onglets + registre de colonnes +
    lignes d'en-tête)."""
    path = project.reference_path or None
    return ReferenceOut(
        path=path,
        sheets=sheet_names(path) if path else [],
        columns=[ReferenceColumnDef(**c) for c in reference_columns_for(project)],
        header_rows=_header_rows(project),
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
    header_row: Optional[int] = Query(
        None, ge=1,
        description="Ligne d'en-tête (1-based) à utiliser ; défaut = ligne "
                    "persistée pour cet onglet, sinon détection auto.",
    ),
    db: Session = Depends(get_db),
) -> list[SheetColumnOut]:
    """Colonnes (lettre + en-tête) d'un onglet du référentiel — alimente les
    menus déroulants « Colonne » de l'éditeur de mapping. La ligne d'en-tête
    suit `header_row` si fourni, sinon la ligne persistée pour cet onglet,
    sinon la détection auto."""
    project = _project_or_404(db, project_id)
    if not project.reference_path:
        return []
    hr = header_row if header_row is not None else _header_rows(project).get(sheet)
    return [SheetColumnOut(**c)
            for c in sheet_columns(project.reference_path, sheet, hr)]


@router.get(
    "/projects/{project_id}/reference/preview",
    response_model=SheetPreviewOut,
)
def get_reference_sheet_preview(
    project_id: uuid.UUID,
    sheet: str = Query(..., description="Titre exact de l'onglet du référentiel"),
    rows: int = Query(15, ge=1, le=25, description="Nombre de lignes d'aperçu"),
    db: Session = Depends(get_db),
) -> SheetPreviewOut:
    """Aperçu des premières lignes d'un onglet pour désigner visuellement la
    ligne d'en-tête (clic sur une ligne dans l'éditeur de mapping)."""
    project = _project_or_404(db, project_id)
    if not project.reference_path:
        return SheetPreviewOut()
    return SheetPreviewOut(**sheet_preview(project.reference_path, sheet, rows))


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
            "Les colonnes script et element doivent etre sur le meme onglet "
            "(le check element les aligne ligne a ligne).",
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

    # Lignes d'en-tête par onglet (1-based). On ne conserve que les entrées
    # valides (≥ 1) ; vide => NULL (détection auto).
    header_rows: dict[str, int] = {}
    for sheet, row in (body.header_rows or {}).items():
        try:
            n = int(row)
        except (ValueError, TypeError):
            continue
        name = str(sheet).strip()
        if name and n >= 1:
            header_rows[name] = n
    project.reference_header_rows = (
        json.dumps(header_rows, ensure_ascii=False) if header_rows else None
    )

    db.commit()
    return _reference_out(project)


@router.delete("/projects/{project_id}/reference", status_code=204, response_class=Response)
def delete_reference(project_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    project = _project_or_404(db, project_id)
    project.reference_path = None
    db.commit()
    return Response(status_code=204)


def _basl_header_rows(project: Project) -> dict[str, int]:
    """Map {onglet: ligne(1-based)} des lignes d'en-tête BASL. `{}` si non
    renseigné ou JSON corrompu (→ détection auto côté parser)."""
    try:
        data = json.loads(project.basl_header_rows or "{}")
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in data.items():
        try:
            n = int(v)
        except (ValueError, TypeError):
            continue
        if n >= 1:
            out[str(k)] = n
    return out


def _basl_out(project: Project) -> ReferenceOut:
    """`ReferenceOut` complet de la BASL (chemin + onglets + registre de
    colonnes + lignes d'en-tête) — même contrat que le référentiel."""
    path = project.basl_path or None
    return ReferenceOut(
        path=path,
        sheets=sheet_names(path) if path else [],
        columns=[ReferenceColumnDef(**c) for c in basl_columns_for(project)],
        header_rows=_basl_header_rows(project),
    )


@router.post("/projects/{project_id}/basl", response_model=ReferenceOut)
def upload_basl(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ReferenceOut:
    """Attache (ou remplace) le fichier BASL du projet. Les checks rechanges /
    outillages / infrastructure / en-tête cross-checkent contre ce fichier. Le
    mapping des colonnes (onglet + colonne) se règle ensuite via
    `PUT /basl/mapping` à partir des onglets renvoyés ici."""
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
    return _basl_out(project)


@router.get("/projects/{project_id}/basl", response_model=ReferenceOut)
def get_basl(project_id: uuid.UUID, db: Session = Depends(get_db)) -> ReferenceOut:
    return _basl_out(_project_or_404(db, project_id))


@router.get(
    "/projects/{project_id}/basl/columns",
    response_model=list[SheetColumnOut],
)
def get_basl_sheet_columns(
    project_id: uuid.UUID,
    sheet: str = Query(..., description="Titre exact de l'onglet de la BASL"),
    header_row: Optional[int] = Query(
        None, ge=1,
        description="Ligne d'en-tête (1-based) à utiliser ; défaut = ligne "
                    "persistée pour cet onglet, sinon détection auto.",
    ),
    db: Session = Depends(get_db),
) -> list[SheetColumnOut]:
    """Colonnes (lettre + en-tête) d'un onglet de la BASL — alimente les menus
    déroulants « Colonne » de l'éditeur de mapping BASL."""
    project = _project_or_404(db, project_id)
    if not project.basl_path:
        return []
    hr = header_row if header_row is not None else _basl_header_rows(project).get(sheet)
    return [SheetColumnOut(**c)
            for c in sheet_columns(project.basl_path, sheet, hr)]


@router.get(
    "/projects/{project_id}/basl/preview",
    response_model=SheetPreviewOut,
)
def get_basl_sheet_preview(
    project_id: uuid.UUID,
    sheet: str = Query(..., description="Titre exact de l'onglet de la BASL"),
    rows: int = Query(15, ge=1, le=25, description="Nombre de lignes d'aperçu"),
    db: Session = Depends(get_db),
) -> SheetPreviewOut:
    """Aperçu des premières lignes d'un onglet de la BASL pour désigner
    visuellement la ligne d'en-tête (clic sur une ligne dans l'éditeur)."""
    project = _project_or_404(db, project_id)
    if not project.basl_path:
        return SheetPreviewOut()
    return SheetPreviewOut(**sheet_preview(project.basl_path, sheet, rows))


@router.put("/projects/{project_id}/basl/mapping", response_model=ReferenceOut)
def update_basl_mapping(
    project_id: uuid.UUID,
    body: ReferenceMappingIn,
    db: Session = Depends(get_db),
) -> ReferenceOut:
    """Enregistre le registre des colonnes BASL (onglet + colonne de chaque
    entrée). Les 3 colonnes builtin (rechange / outillage / infrastructure)
    sont toujours conservées ; les colonnes ajoutées doivent porter un nom
    unique en `[A-Za-z][A-Za-z0-9_]*`. Une colonne builtin non mappée
    (onglet/colonne vide) fait retomber le check sur l'union de toutes les
    cellules de la BASL."""
    project = _project_or_404(db, project_id)
    incoming = {c.name.strip(): c for c in body.columns}

    registry: list[dict] = []
    for name in BASL_BUILTIN_COLUMN_NAMES:
        c = incoming.get(name)
        sheet = c.sheet.strip() if c else ""
        column = c.column.strip() if c else ""
        registry.append({"name": name, "sheet": sheet, "column": column, "builtin": True})

    seen: set[str] = set(BASL_BUILTIN_COLUMN_NAMES)
    for c in body.columns:
        name = c.name.strip()
        if not name or name in BASL_BUILTIN_COLUMN_NAMES:
            continue
        if not _COLUMN_NAME_RE.match(name):
            raise AppError(
                "BASL_MAPPING_INVALID",
                f"Nom de colonne invalide : « {name} ». Lettres, chiffres et "
                "« _ » uniquement, en commencant par une lettre.",
                status_code=400, detail={"name": name},
            )
        if name in seen:
            raise AppError(
                "BASL_MAPPING_INVALID",
                f"Nom de colonne en double : « {name} ».",
                status_code=400, detail={"name": name},
            )
        seen.add(name)
        registry.append({
            "name": name, "sheet": c.sheet.strip(),
            "column": c.column.strip(), "builtin": False,
        })

    project.basl_columns = json.dumps(registry, ensure_ascii=False)

    header_rows: dict[str, int] = {}
    for sheet, row in (body.header_rows or {}).items():
        try:
            n = int(row)
        except (ValueError, TypeError):
            continue
        name = str(sheet).strip()
        if name and n >= 1:
            header_rows[name] = n
    project.basl_header_rows = (
        json.dumps(header_rows, ensure_ascii=False) if header_rows else None
    )

    db.commit()
    return _basl_out(project)


@router.delete("/projects/{project_id}/basl", status_code=204, response_class=Response)
def delete_basl(project_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    project = _project_or_404(db, project_id)
    project.basl_path = None
    db.commit()
    return Response(status_code=204)
