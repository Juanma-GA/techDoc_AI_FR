"""Documents API — upload / list / get / pdf / export / rollback / history."""

import uuid
import tempfile
from pathlib import Path
from typing import Any, Literal, Optional

import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.checks.client_registry import (
    LoadedClientConfiguration,
    active_standard_versions,
)
from app.checks.client_bundle import ClientMapping, ClientMappingField
from app.config import settings
from app.core import doc_convert, docx_pipeline, docx_versioning, ingest
from app.core.document_context import (
    DOCUMENT_CONTEXT_FIELDS,
    get_document_context_defaults,
    save_document_context_defaults,
)
from app.core.errors import AppError
from app.core.pdf_versioning import current_path, init_storage, path_for
from app.core.regex_safety import USER_REGEX_TIMEOUT_SECONDS, compile_user_regex
from app.core.security import read_upload_bounded
from app.core.versioning import sha256_of_bytes
from app.db.models import Document, EditHistory, StandardVersion
from app.db.session import get_db
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf
from app.schemas import DocumentMetaPatchIn, DocumentOut, EditHistoryOut, RollbackIn


router = APIRouter(tags=["documents"])


_MAX_BATCH_SIZE = 20


def _legacy_metadata_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip()) or None
    return str(value).strip()


def _validate_client_metadata_patch(
    values: dict[str, Any],
    field_definitions: dict[str, ClientMappingField],
) -> None:
    for key, value in values.items():
        definition = field_definitions.get(key)
        if definition is None:
            raise AppError(
                "CLIENT_METADATA_INVALID",
                f"Le champ de métadonnées '{key}' n'est pas déclaré par le client actif.",
                detail={"field": key, "reason": "undeclared"},
                status_code=422,
            )
        if value is None:
            continue

        if definition.type in {"string", "enum"}:
            value_is_valid = isinstance(value, str)
        elif definition.type == "string_list":
            value_is_valid = isinstance(value, list) and all(
                isinstance(item, str) for item in value
            )
        elif definition.type == "integer":
            value_is_valid = type(value) is int
        elif definition.type == "number":
            value_is_valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            value_is_valid = type(value) is bool

        if not value_is_valid:
            raise AppError(
                "CLIENT_METADATA_INVALID",
                f"Valeur invalide pour le champ de métadonnées '{key}'.",
                detail={"field": key, "expected": definition.type},
                status_code=422,
            )
        if definition.max_length is not None and len(value) > definition.max_length:
            value_is_valid = False
        if definition.max_items is not None and len(value) > definition.max_items:
            value_is_valid = False
        if definition.allowed_values is not None:
            candidates = value if definition.type == "string_list" else [value]
            if any(item not in definition.allowed_values for item in candidates):
                value_is_valid = False
        if definition.pattern is not None and value_is_valid:
            candidates = value if definition.type == "string_list" else [value]
            pattern = compile_user_regex(definition.pattern)
            try:
                if any(
                    pattern.fullmatch(item, timeout=USER_REGEX_TIMEOUT_SECONDS) is None
                    for item in candidates
                ):
                    value_is_valid = False
            except TimeoutError:
                value_is_valid = False
        if not value_is_valid:
            raise AppError(
                "CLIENT_METADATA_INVALID",
                f"Valeur invalide pour le champ de métadonnées '{key}'.",
                detail={"field": key, "expected": definition.type},
                status_code=422,
            )


def _resolve_standard_versions(
    standard_version_id: Optional[uuid.UUID],
    standard_version_ids: Optional[str],
    db: Session,
    client_configuration: LoadedClientConfiguration | None = None,
) -> tuple[Optional[uuid.UUID], list[uuid.UUID]]:
    """Resolve the multi-norm payload into a validated (primary, [all]) pair.

    `standard_version_id` (single, legacy) and `standard_version_ids`
    (comma-separated, v2 multi-norm) can be combined: every value listed
    is validated against the DB, the *first* one becomes the « primary »
    that stays in `Document.standard_version_id` for backward compat. With
    no explicit selection, the active bundle manifest supplies the defaults.
    """
    raw_ids: list[uuid.UUID] = []
    if standard_version_id is not None:
        raw_ids.append(standard_version_id)
    if standard_version_ids:
        for token in standard_version_ids.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                raw_ids.append(uuid.UUID(token))
            except ValueError as exc:
                raise AppError(
                    "STANDARD_VERSION_INVALID",
                    f"UUID de version de norme invalide : {token}",
                    status_code=400,
                ) from exc

    # De-duplicate while preserving order.
    seen: set[uuid.UUID] = set()
    deduped: list[uuid.UUID] = []
    for vid in raw_ids:
        if vid in seen:
            continue
        seen.add(vid)
        deduped.append(vid)

    for vid in deduped:
        if db.get(StandardVersion, vid) is None:
            raise AppError(
                "STANDARD_VERSION_NOT_FOUND",
                "Version de norme introuvable",
                status_code=400,
            )
    if not deduped:
        deduped = [
            version.id
            for version in active_standard_versions(db, client_configuration)
        ]
    primary = deduped[0] if deduped else None
    return primary, deduped


def _persist_pdf(
    pdf_bytes: bytes,
    display_name: str,
    target: str,
    db: Session,
    standard_version_id: Optional[uuid.UUID] = None,
    standard_version_ids: Optional[list[uuid.UUID]] = None,
    convert_engine: str = "pdf",
    source_format: str = "pdf",
    original_data: Optional[bytes] = None,
    client_mapping: ClientMapping | None = None,
) -> Document:
    """Persist a **PDF** (native or converted from Word) as a new `Document` row.

    The stored artifact is always the faithful PDF — page count, signature
    check and the **quality gate** (text-layer coverage → reviewability state)
    run on it. `display_name` keeps the original upload name (incl. a
    `.doc/.docx` extension) for traceability. `convert_engine` traces the
    normalisation engine ("pdf" native, "libreoffice", "word").
    """
    from app.core import quality_gate

    sha = sha256_of_bytes(pdf_bytes)
    doc_id = uuid.uuid4()
    storage_dir_value = f"document_{doc_id.hex}"
    init_storage(storage_dir_value, pdf_bytes)

    try:
        opened = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise AppError("PDF_INVALID", "PDF illisible", status_code=400) from exc
    try:
        if _has_signature(opened):
            raise AppError(
                "PDF_HAS_SIGNATURE",
                "Les PDF signés numériquement ne peuvent pas être édités",
                status_code=400,
            )
        page_count = opened.page_count
        # Portail qualite : mesure la couverture texte AVANT fermeture. Un doc
        # sans couche texte (scan) est marque "unusable" -> l'analyse le signale
        # au lieu de rendre zero anomalie silencieusement.
        report = quality_gate.assess(opened)
    finally:
        opened.close()

    import json as _json
    context_defaults = get_document_context_defaults(db, client_mapping)

    document = Document(
        id=doc_id,
        original_filename=display_name,
        sha256=sha,
        storage_dir=storage_dir_value,
        page_count=page_count,
        target_unit_system=target,
        standard_version_id=standard_version_id,
        standard_version_ids=_json.dumps([str(v) for v in (standard_version_ids or [])]),
        status="uploaded",
        current_version=0,
        source_format=source_format,
        working_format="pdf",
        original_sha256=sha256_of_bytes(original_data if original_data is not None else pdf_bytes),
        original_storage_path=str(path_for(storage_dir_value, 0)),
        convert_engine=convert_engine,
        text_coverage=report.coverage,
        quality=report.state,
        client_metadata=dict(context_defaults),
        meta_revision_date=context_defaults.get("meta_revision_date"),
        meta_cmm_number=context_defaults.get("meta_cmm_number"),
        meta_first_issue_date=context_defaults.get("meta_first_issue_date"),
        meta_last_issue_date=context_defaults.get("meta_last_issue_date"),
        meta_revision_number=context_defaults.get("meta_revision_number"),
        meta_pnr_number=_legacy_metadata_value(context_defaults.get("meta_pnr_number")),
        meta_manufacturer=context_defaults.get("meta_manufacturer", "Airbus"),
        document_language=context_defaults.get("document_language"),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _ingest_and_persist(
    name: str,
    data: bytes,
    target: str,
    db: Session,
    standard_version_id: Optional[uuid.UUID] = None,
    standard_version_ids: Optional[list[uuid.UUID]] = None,
    source_format: str = "pdf",
    original_data: Optional[bytes] = None,
) -> Document:
    """Normalize one supported file (.pdf/.doc/.docx) to a faithful PDF, persist it.

    `.doc/.docx` go through LibreOffice / Word COM conversion (may be slow) —
    this runs inside FastAPI's sync threadpool, off the async loop.
    """
    pdf_bytes, display_name, engine = ingest.to_pdf_bytes(name, data)
    return _persist_pdf(
        pdf_bytes, display_name, target, db,
        standard_version_id=standard_version_id,
        standard_version_ids=standard_version_ids,
        convert_engine=engine,
        source_format=source_format,
        original_data=original_data,
    )


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _persist_docx(
    name: str,
    data: bytes,
    target: str,
    db: Session,
    standard_version_id: Optional[uuid.UUID] = None,
    standard_version_ids: Optional[list[uuid.UUID]] = None,
    original_data: Optional[bytes] = None,
    source_format: Optional[str] = None,
    engine_override: Optional[str] = None,
    client_mapping: ClientMapping | None = None,
) -> Document:
    """Persist a DOCX working document while retaining the detected source.

    `.docx` : le fichier de travail est stocke tel quel en v0.docx,
    parse pour compter les blocs/pages — aucune conversion.

    `.doc` (legacy binaire) : converti **une seule fois, en interne** en
    `.docx` via Word ou LibreOffice (`doc_convert.office_to_docx_bytes`) pour pouvoir
    beneficier de la revue native au lieu d'etre bascule vers le pipeline PDF.
    L'utilisateur n'a rien a convertir lui-meme : `original_filename` garde
    l'extension `.doc` d'origine, et l'export (`GET .../export`) reconvertit
    le `.docx` de travail en `.doc` avant de le renvoyer (cf. `export_pdf`).
    """
    from app.core.security import safe_filename

    safe = safe_filename(name)
    ext = Path(safe).suffix.lower()
    if source_format is None and ext not in (".docx", ".doc"):
        raise AppError(
            "DOCX_MODE_REQUIRES_DOCX",
            "Le mode Word natif n'accepte que des fichiers .doc ou .docx.",
            status_code=400,
        )
    if len(data) == 0:
        raise AppError("UPLOAD_EMPTY", "Fichier vide", status_code=400)
    if len(data) > settings.max_upload_size_bytes:
        raise AppError("FILE_TOO_LARGE", f"{safe} depasse la taille max.", status_code=413)

    if source_format is not None:
        working_data = data
        engine = engine_override or "docx-native"
    elif ext == ".doc":
        # Conversion interne .doc -> .docx (silencieuse pour l'utilisateur) :
        # le fichier de travail est du docx, mais `original_filename` conserve
        # le suffixe .doc pour un aller-retour transparent a l'export.
        working_data, _ = doc_convert.office_to_docx_bytes(data, ".doc")
        engine = "docx-native-from-doc"
    else:
        if data[:2] != b"PK":
            raise AppError("DOCX_INVALID", "Fichier .docx illisible (OOXML attendu).", status_code=400)
        working_data = data
        engine = "docx-native"

    sha = sha256_of_bytes(working_data)
    doc_id = uuid.uuid4()
    storage_dir_value = f"document_{doc_id.hex}"
    docx_versioning.write_version(storage_dir_value, 0, working_data)
    source_data = original_data if original_data is not None else data
    original_path = docx_versioning.write_original(storage_dir_value, source_data, safe)
    try:
        parsed = parse_docx(docx_versioning.version_path(storage_dir_value, 0))
    except Exception as exc:  # noqa: BLE001
        raise AppError("DOCX_INVALID", f"{safe} n'est pas lisible.", status_code=400) from exc

    page_count = max((b.page for b in parsed.blocks), default=1)

    import json as _json
    context_defaults = get_document_context_defaults(db, client_mapping)

    document = Document(
        id=doc_id,
        original_filename=safe,
        sha256=sha,
        storage_dir=storage_dir_value,
        page_count=page_count,
        target_unit_system=target,
        standard_version_id=standard_version_id,
        standard_version_ids=_json.dumps([str(v) for v in (standard_version_ids or [])]),
        status="uploaded",
        current_version=0,
        source_format=source_format or "docx",
        working_format="docx",
        original_sha256=sha256_of_bytes(source_data),
        original_storage_path=str(original_path),
        convert_engine=engine,
        text_coverage=100,
        quality="analyzable",
        client_metadata=dict(context_defaults),
        meta_revision_date=context_defaults.get("meta_revision_date"),
        meta_cmm_number=context_defaults.get("meta_cmm_number"),
        meta_first_issue_date=context_defaults.get("meta_first_issue_date"),
        meta_last_issue_date=context_defaults.get("meta_last_issue_date"),
        meta_revision_number=context_defaults.get("meta_revision_number"),
        meta_pnr_number=_legacy_metadata_value(context_defaults.get("meta_pnr_number")),
        meta_manufacturer=context_defaults.get("meta_manufacturer", "Airbus"),
        document_language=context_defaults.get("document_language"),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.post("/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    target: Literal["metric", "imperial", "auto", "none"] = Query(default="none"),
    standard_version_id: Optional[uuid.UUID] = Query(default=None),
    standard_version_ids: Optional[str] = Query(
        default=None,
        description="Comma-separated UUIDs of standard versions to apply at analyse",
    ),
    db: Session = Depends(get_db),
) -> Document:
    primary, all_ids = _resolve_standard_versions(
        standard_version_id,
        standard_version_ids,
        db,
        request.app.state.client_configuration,
    )
    name = file.filename or "upload"
    if name.lower().endswith(".zip"):
        raise AppError(
            "USE_BATCH",
            "Les archives .zip doivent etre envoyees via /documents/batch",
            status_code=400,
        )
    data = read_upload_bounded(file, settings.max_upload_size_bytes)
    prepared = ingest.prepare_document(name, data)
    if prepared.working_format == "docx":
        return _persist_docx(
            prepared.filename, prepared.working_bytes, target, db,
            standard_version_id=primary,
            standard_version_ids=all_ids,
            original_data=prepared.original_bytes,
            source_format=prepared.source_format,
            engine_override=prepared.convert_engine,
            client_mapping=request.app.state.client_configuration.mapping,
        )
    return _persist_pdf(
        prepared.working_bytes, prepared.filename, target, db,
        standard_version_id=primary,
        standard_version_ids=all_ids,
        convert_engine=prepared.convert_engine,
        source_format=prepared.source_format,
        original_data=prepared.original_bytes,
        client_mapping=request.app.state.client_configuration.mapping,
    )


@router.post("/documents/batch")
def upload_documents_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    target: Literal["metric", "imperial", "auto", "none"] = Query(default="none"),
    standard_version_id: Optional[uuid.UUID] = Query(default=None),
    standard_version_ids: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Upload many files at once — `.pdf/.doc/.docx` and `.zip` archives. Zips are
    expanded, Word files converted to a faithful PDF. Per-file failures are
    returned in `failed` rather than rolling everything back — partial success
    is intended. `ignored` lists archive members with an unsupported extension."""
    if not files:
        raise AppError("UPLOAD_EMPTY", "Aucun fichier reçu", status_code=400)
    if len(files) > _MAX_BATCH_SIZE:
        raise AppError(
            "UPLOAD_BATCH_TOO_LARGE",
            f"Maximum {_MAX_BATCH_SIZE} fichiers par batch",
            status_code=400,
        )

    primary, all_ids = _resolve_standard_versions(
        standard_version_id,
        standard_version_ids,
        db,
        request.app.state.client_configuration,
    )
    created: list[dict] = []
    failed: list[dict] = []
    ignored: list[str] = []
    expanded_count = 0
    for upload in files:
        upload_name = upload.filename or "upload"
        try:
            raw = read_upload_bounded(upload, settings.max_upload_size_bytes)
            expanded, file_ignored = ingest.expand_uploads(
                [(upload_name, raw)],
                max_total_uncompressed=settings.max_upload_size_bytes,
                allow_empty=True,
            )
            ignored.extend(file_ignored)
            if expanded_count + len(expanded) > ingest.MAX_FILES:
                raise AppError(
                    "TOO_MANY_FILES",
                    f"Plus de {ingest.MAX_FILES} fichiers dans l'upload.",
                    status_code=413,
                )
            expanded_count += len(expanded)
        except AppError as exc:
            failed.append({"filename": upload_name, "code": exc.code, "message": exc.message})
            continue

        for name, data in expanded:
            try:
                prepared = ingest.prepare_document(name, data)
                if prepared.working_format == "docx":
                    doc = _persist_docx(
                        prepared.filename, prepared.working_bytes, target, db,
                        standard_version_id=primary,
                        standard_version_ids=all_ids,
                        original_data=prepared.original_bytes,
                        source_format=prepared.source_format,
                        engine_override=prepared.convert_engine,
                        client_mapping=request.app.state.client_configuration.mapping,
                    )
                else:
                    doc = _persist_pdf(
                        prepared.working_bytes, prepared.filename, target, db,
                        standard_version_id=primary,
                        standard_version_ids=all_ids,
                        convert_engine=prepared.convert_engine,
                        source_format=prepared.source_format,
                        original_data=prepared.original_bytes,
                        client_mapping=request.app.state.client_configuration.mapping,
                    )
                created.append(DocumentOut.model_validate(doc).model_dump(mode="json"))
            except AppError as exc:
                failed.append({"filename": name, "code": exc.code, "message": exc.message})
            except Exception as exc:  # noqa: BLE001
                failed.append(
                    {
                        "filename": name,
                        "code": "INTERNAL_ERROR",
                        "message": "Erreur interne pendant le traitement du fichier.",
                    }
                )

    if not created and not failed:
        raise AppError(
            "NO_SUPPORTED_FILE",
            "Aucun fichier .pdf / .doc / .docx trouvé dans l'upload.",
            status_code=400,
        )

    status = 201 if not failed else (207 if created else 400)
    return JSONResponse(
        status_code=status,
        content={"created": created, "failed": failed, "ignored": ignored},
    )


def _has_signature(doc: fitz.Document) -> bool:
    try:
        if hasattr(doc, "get_signatures"):
            return bool(doc.get_signatures())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return False
    return False


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    return doc


@router.patch("/documents/{document_id}", response_model=DocumentOut)
def patch_document_meta(
    document_id: uuid.UUID,
    request: Request,
    body: DocumentMetaPatchIn,
    db: Session = Depends(get_db),
) -> Document:
    """Enregistre le mapping manuel et la langue du document."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    patch = body.model_dump(exclude_unset=True)
    client_metadata_patch = patch.pop("client_metadata", {})
    client_mapping = request.app.state.client_configuration.mapping
    _validate_client_metadata_patch(
        client_metadata_patch,
        client_mapping.fields,
    )
    metadata_updates = dict(client_metadata_patch)
    legacy_updates = {
        key: value for key, value in patch.items() if key in DOCUMENT_CONTEXT_FIELDS
    }
    for key, value in legacy_updates.items():
        definition = client_mapping.fields.get(key)
        if definition is not None and definition.type == "string_list":
            if isinstance(value, str):
                metadata_updates[key] = [
                    item.strip() for item in value.split(",") if item.strip()
                ]
            else:
                metadata_updates[key] = []
        else:
            metadata_updates[key] = value

    client_metadata = dict(doc.client_metadata or {})
    client_metadata.update(metadata_updates)
    doc.client_metadata = client_metadata
    for key, value in metadata_updates.items():
        if key in DOCUMENT_CONTEXT_FIELDS:
            setattr(doc, key, _legacy_metadata_value(value))

    db.commit()
    context_updates = {
        key: value
        for key, value in metadata_updates.items()
        if key in DOCUMENT_CONTEXT_FIELDS
    }
    if context_updates:
        save_document_context_defaults(db, context_updates, client_mapping)
    db.refresh(doc)
    return doc


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    storage_dir = doc.storage_dir
    db.delete(doc)
    db.commit()
    # Cleanup the snapshot folder on disk too — otherwise an admin
    # « Tout supprimer » leaves orphan `document_*/v0.pdf` files
    # cluttering the data directory. Use the admin helper so the
    # Windows read-only bit on v0.pdf is handled correctly.
    from app.api.admin import _remove_storage_dir as _rm_storage

    _rm_storage(storage_dir)


@router.get("/documents/{document_id}/pdf")
def get_pdf(
    document_id: uuid.UUID,
    version: str = Query(default="current"),
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    if doc.working_format != "pdf":
        raise AppError(
            "EXPORT_FORMAT_UNAVAILABLE",
            "Ce document a un DOCX comme format de travail; utilisez l'export PDF explicite.",
            status_code=409,
        )

    if version == "current":
        target = current_path(doc.storage_dir, doc.current_version)
    elif version == "original":
        target = path_for(doc.storage_dir, 0)
    else:
        try:
            n = int(version)
        except ValueError as exc:
            raise AppError("VERSION_INVALID", "Version invalide", status_code=400) from exc
        target = path_for(doc.storage_dir, n)

    if not target.is_file():
        raise AppError("PDF_VERSION_MISSING", "Snapshot absent", status_code=404)

    return FileResponse(
        target,
        media_type="application/pdf",
        filename=doc.original_filename,
    )


@router.get("/documents/{document_id}/pages/{page_number}.png")
def render_page_png(
    document_id: uuid.UUID,
    page_number: int,
    dpi: int = Query(default=120, ge=72, le=300),
    db: Session = Depends(get_db),
) -> Response:
    """Rasterize one page of the current PDF to PNG.

    Used by the preview HTML viewer to overlay suggestion bboxes over a
    bitmap rendering of the page (no PDF.js dependency).
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    if doc.working_format != "pdf":
        raise AppError(
            "EXPORT_FORMAT_UNAVAILABLE",
            "Le rendu page PNG est disponible pour un document de travail PDF uniquement.",
            status_code=409,
        )
    if page_number < 1 or page_number > doc.page_count:
        raise AppError(
            "PDF_PAGE_OUT_OF_RANGE",
            f"Page {page_number} hors limites (1..{doc.page_count})",
            status_code=400,
        )

    src = current_path(doc.storage_dir, doc.current_version)
    pdf = fitz.open(src)
    try:
        page = pdf.load_page(page_number - 1)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        png_bytes = pix.tobytes("png")
    finally:
        pdf.close()

    etag = f'"{doc.id.hex}:{doc.current_version}:{page_number}:{dpi}"'
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=60", "ETag": etag},
    )


def _commented_pdf_response(doc: Document, db: Session) -> Response:
    from app.core.pdf_annotate import build_commented_pdf
    from app.db.models import Suggestion as SuggestionModel

    suggestions = list(db.scalars(
        select(SuggestionModel)
        .where(SuggestionModel.document_id == doc.id, SuggestionModel.status != "rejected")
        .order_by(SuggestionModel.page, SuggestionModel.span_index)
    ))
    if doc.working_format == "pdf":
        pdf_path = current_path(doc.storage_dir, doc.current_version)
        pdf_bytes = build_commented_pdf(str(pdf_path), suggestions)
    else:
        working = docx_versioning.version_path(doc.storage_dir, doc.current_version)
        if not working.is_file():
            raise AppError("DOCX_VERSION_MISSING", "DOCX courant absent", status_code=404)
        with tempfile.TemporaryDirectory(prefix="dr_commented_") as temp_dir:
            converted, _ = doc_convert.doc_to_pdf_bytes(working.read_bytes(), ".docx")
            pdf_path = Path(temp_dir) / "working.pdf"
            pdf_path.write_bytes(converted)
            pdf_bytes = build_commented_pdf(str(pdf_path), suggestions)
    stem = Path(doc.original_filename).stem
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{stem}_commente.pdf"'},
    )


@router.get("/documents/{document_id}/exports")
def list_document_exports(document_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Return exports supported by the current state and their conversion warnings."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    available: list[dict[str, str]] = []
    if doc.source_format == "doc" and doc.original_storage_path:
        available.append({"kind": "original", "format": "doc", "label": "DOC original", "warning": ""})
    elif doc.source_format == "pdf":
        available.append({"kind": "original", "format": "pdf", "label": "PDF original", "warning": ""})
    elif doc.source_format == "docx":
        available.append({"kind": "original", "format": "docx", "label": "DOCX original", "warning": ""})
    if doc.working_format == "pdf":
        available.append({"kind": "commented", "format": "pdf", "label": "PDF commente", "warning": ""})
        if doc.has_applied_edits:
            available.append({"kind": "corrected", "format": "pdf", "label": "PDF corrige", "warning": ""})
    else:
        available.append({"kind": "commented", "format": "pdf", "label": "PDF commente", "warning": "Conversion Word -> PDF : le rendu peut varier selon le moteur de conversion (Word ou LibreOffice)."})
        if doc.has_applied_edits:
            available.append({"kind": "corrected", "format": "docx", "label": "DOCX corrige", "warning": ""})
            available.append({"kind": "corrected", "format": "pdf", "label": "PDF corrige", "warning": "Conversion Word -> PDF : le rendu peut varier selon le moteur de conversion (Word ou LibreOffice)."})
    if doc_convert.can_convert_formats():
        if doc.working_format == "pdf":
            available.append({"kind": "converted", "format": "docx", "label": "DOCX converti", "warning": "Conversion PDF -> DOCX : mise en page, tableaux, polices et positionnement peuvent etre modifies."})
        available.append({"kind": "converted", "format": "doc", "label": "DOC converti", "warning": "Conversion vers DOC legacy : degradation possible de la mise en page, des polices et des elements avances."})
    return {
        "source_format": doc.source_format,
        "working_format": doc.working_format,
        "has_applied_edits": doc.has_applied_edits,
        "available": available,
    }


@router.get("/documents/{document_id}/export", response_model=None)
def export_pdf(
    document_id: uuid.UUID,
    format: Optional[Literal["original", "corrected", "commented", "pdf", "docx", "doc"]] = Query(default=None),
    db: Session = Depends(get_db),
) -> FileResponse | Response:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    if format == "commented":
        return _commented_pdf_response(doc, db)
    requested = format or "corrected"
    if requested == "original":
        if doc.source_format == "pdf":
            target = path_for(doc.storage_dir, 0)
            return FileResponse(target, media_type="application/pdf", filename=doc.original_filename)
        original = Path(doc.original_storage_path or "")
        if not original.is_file():
            raise AppError("ORIGINAL_FILE_MISSING", "Fichier original absent", status_code=404)
        media = "application/msword" if doc.source_format == "doc" else _DOCX_MIME
        return FileResponse(original, media_type=media, filename=doc.original_filename)
    if requested == "pdf" and doc.working_format != "pdf":
        if not docx_versioning.version_path(doc.storage_dir, doc.current_version).is_file():
            raise AppError("DOCX_VERSION_MISSING", "DOCX courant absent", status_code=404)
        converted, _ = doc_convert.doc_to_pdf_bytes(
            docx_versioning.read_version(doc.storage_dir, doc.current_version), ".docx"
        )
        return Response(content=converted, media_type="application/pdf")
    if requested not in {"corrected", "pdf", "docx", "doc"}:
        raise AppError("EXPORT_FORMAT_UNAVAILABLE", "Format d'export incompatible.", status_code=409)
    # Pipeline Word natif : on rend le .docx corrige (version courante). Si le
    # document d'origine etait un `.doc` (converti en interne a l'upload, cf.
    # `_persist_docx`), on reconvertit le .docx de travail en .doc a la volee
    # pour que l'utilisateur recupere le format qu'il a envoye, sans etape
    # manuelle de conversion de sa part.
    if doc.working_format == "docx":
        target = docx_versioning.version_path(doc.storage_dir, doc.current_version)
        if not target.is_file():
            raise AppError("DOCX_VERSION_MISSING", "DOCX courant absent", status_code=404)
        if requested == "doc":
            doc_bytes = doc_convert.docx_to_doc_bytes(target.read_bytes())
            return Response(
                content=doc_bytes,
                media_type="application/msword",
                headers={"Content-Disposition": f'attachment; filename="{doc.original_filename}"'},
            )
        if requested == "pdf":
            converted, _ = doc_convert.doc_to_pdf_bytes(target.read_bytes(), ".docx")
            return Response(content=converted, media_type="application/pdf")
        if requested not in {"corrected", "docx"}:
            raise AppError("EXPORT_FORMAT_UNAVAILABLE", "Format d'export incompatible.", status_code=409)
        return FileResponse(
            target,
            media_type=_DOCX_MIME,
            filename=doc.original_filename,
            headers={"Content-Disposition": f'attachment; filename="{doc.original_filename}"'},
        )
    # Pipeline PDF (defaut, y compris pour un .doc/.docx converti a l'upload) :
    # le livrable est toujours un PDF -> le nom rendu porte l'extension .pdf,
    # jamais l'extension Word d'origine (sinon le fichier telecharge s'appelle
    # "manuel.doc" alors que son contenu est un PDF, illisible tel quel dans Word).
    target = current_path(doc.storage_dir, doc.current_version)
    if requested == "docx" and doc.working_format == "pdf":
        return Response(
            content=doc_convert.pdf_to_docx_bytes(target.read_bytes()),
            media_type=_DOCX_MIME,
            headers={"Content-Disposition": f'attachment; filename="{Path(doc.original_filename).stem}.docx"'},
        )
    if requested == "doc" and doc.working_format == "pdf":
        return Response(
            content=doc_convert.pdf_to_doc_bytes(target.read_bytes()),
            media_type="application/msword",
            headers={"Content-Disposition": f'attachment; filename="{Path(doc.original_filename).stem}.doc"'},
        )
    if requested == "doc" and doc.working_format == "docx":
        working = docx_versioning.read_version(doc.storage_dir, doc.current_version)
        return Response(
            content=doc_convert.docx_to_doc_bytes(working),
            media_type="application/msword",
            headers={"Content-Disposition": f'attachment; filename="{Path(doc.original_filename).stem}.doc"'},
        )
    pdf_filename = Path(doc.original_filename).stem + ".pdf"
    return FileResponse(
        target,
        media_type="application/pdf",
        filename=pdf_filename,
        headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'},
    )


@router.get("/documents/{document_id}/blocks")
def get_docx_blocks(document_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Vue blocs d'un document Word natif (reviewer Phase 1). 400 si le document
    n'est pas en pipeline docx."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    if doc.working_format != "docx":
        raise AppError(
            "NOT_DOCX_DOCUMENT",
            "Ce document n'est pas en pipeline Word natif.",
            status_code=400,
        )
    src = docx_versioning.version_path(doc.storage_dir, doc.current_version)
    if not src.is_file():
        raise AppError("DOCX_VERSION_MISSING", "DOCX courant absent", status_code=404)
    parsed = parse_docx(src)
    return {"blocks": docx_pipeline.block_view(parsed)}


@router.get("/documents/{document_id}/commented.pdf")
def export_commented_pdf(document_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """PDF **commente** : le PDF fidele + les anomalies retenues (non rejetees)
    estampillees en annotations, plus une page-sommaire. C'est le livrable sur
    lequel le relecteur s'appuie pour corriger son document Word."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    return _commented_pdf_response(doc, db)


@router.post("/documents/{document_id}/rollback", response_model=DocumentOut)
def rollback_document(
    document_id: uuid.UUID,
    body: RollbackIn,
    db: Session = Depends(get_db),
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    target = (
        docx_versioning.version_path(doc.storage_dir, body.target_version)
        if doc.working_format == "docx"
        else path_for(doc.storage_dir, body.target_version)
    )
    if not target.is_file():
        raise AppError(
            "WORKING_VERSION_MISSING",
            f"Version {body.target_version} introuvable",
            status_code=404,
        )

    previous = doc.current_version
    doc.current_version = body.target_version
    db.add(
        EditHistory(
            document_id=doc.id,
            suggestion_id=None,
            version_before=previous,
            version_after=body.target_version,
            snapshot_path=str(target),
            diff_summary='{"action": "rollback"}',
            rolled_back=True,
        )
    )
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents/{document_id}/history", response_model=list[EditHistoryOut])
def get_history(document_id: uuid.UUID, db: Session = Depends(get_db)) -> list[EditHistory]:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    stmt = (
        select(EditHistory)
        .where(EditHistory.document_id == document_id)
        .order_by(EditHistory.applied_at.desc())
    )
    return list(db.scalars(stmt))


@router.get("/documents/{document_id}/suggestions")
def list_document_suggestions(
    document_id: uuid.UUID,
    status: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    rule_kind: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Filtered suggestion listing scoped to one document.

    Mirrors GET /suggestions?document_id=… but is the canonical front URL.
    """
    from app.db.models import Suggestion as SuggestionModel
    from app.schemas import SuggestionOut

    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)

    stmt = select(SuggestionModel).where(SuggestionModel.document_id == document_id)
    if status:
        stmt = stmt.where(SuggestionModel.status == status)
    if severity:
        stmt = stmt.where(SuggestionModel.severity == severity)
    if rule_kind:
        stmt = stmt.where(SuggestionModel.rule_kind == rule_kind)

    rows = list(db.scalars(stmt.order_by(
        SuggestionModel.page,
        SuggestionModel.span_index,
        SuggestionModel.created_at,
        SuggestionModel.id,
    )))
    return [SuggestionOut.model_validate(r).model_dump(mode="json") for r in rows]


# Parses suggestions endpoint inline to avoid a circular import.
