"""POST /api/v1/documents/{id}/analyze — SSE stream emitting suggestions."""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, SimpleQueue
from typing import Optional

import fitz
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.checks.client_registry import active_standard_versions
from app.checks.mode_registry import (
    analysis_standard_version_ids,
    get_request_client_configuration,
)
from app.config import settings
from app.core.client_metadata import validate_client_metadata_patch
from app.core.compiled_rules import RuleResult
from app.core.demo_scope import get_document_in_current_mode
from app.core.document_context import missing_document_context
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.page_range import (
    filter_docx,
    filter_pdf_pages,
    resolve_page_range,
    select_pdf_page_numbers,
)
from app.core.pdf_versioning import current_path, path_for  # noqa: F401
from app.core.preparation_classification import load_page_classification
from app.core.preparation_check_service import apply_preparation_ocr
from app.core.preparation_state import load_preparation_mapping
from app.core.rules_engine import load_compiled_rules, materialize, run_all
from app.core.security import read_upload_bounded
from app.db.models import AnalysisRun, Document, StandardVersion, Suggestion
from app.db.preparation_models import DocumentPreparation
from app.db.session import SessionLocal, get_db
from app.parsers.pdf_parser import parse_pdf
from app.schemas import SuggestionOut

router = APIRouter(tags=["analyze"])
_logger = get_logger(__name__)


def _parse_page_overrides(raw: str | None, page_count: int) -> dict[int, bool]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise AppError(
            "PAGE_OVERRIDE_INVALID",
            "Les statuts manuels des pages sont invalides.",
            status_code=422,
        ) from exc
    if not isinstance(payload, dict):
        raise AppError(
            "PAGE_OVERRIDE_INVALID",
            "Les statuts manuels des pages sont invalides.",
            status_code=422,
        )
    overrides: dict[int, bool] = {}
    for raw_page, is_modified in payload.items():
        try:
            page = int(raw_page)
        except (TypeError, ValueError) as exc:
            raise AppError(
                "PAGE_OVERRIDE_INVALID",
                "Un numero de page corrige est invalide.",
                status_code=422,
            ) from exc
        if not 1 <= page <= page_count or not isinstance(is_modified, bool):
            raise AppError(
                "PAGE_OVERRIDE_INVALID",
                "Un statut manuel de page est invalide.",
                status_code=422,
            )
        overrides[page] = is_modified
    return overrides


@router.get("/documents/{document_id}/rule-results", response_model=list[RuleResult])
def latest_rule_results(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[RuleResult]:
    if get_document_in_current_mode(db, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    run = db.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.document_id == document_id, AnalysisRun.status == "done")
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    )
    if run is None:
        return []
    try:
        payload = json.loads(run.compiled_rules_snapshot_json or "{}")
        rule_titles = {
            str(rule.get("id")): str(rule.get("topic") or "")
            for rule in payload.get("rules", [])
            if isinstance(rule, dict) and rule.get("id")
        }
        return [
            RuleResult.model_validate(
                {
                    **item,
                    "rule_title": item.get("rule_title") or rule_titles.get(str(item.get("rule_id"))),
                }
            )
            for item in payload.get("results", [])
            if isinstance(item, dict)
        ]
    except (AttributeError, TypeError, ValueError):
        return []


@router.delete(
    "/documents/{document_id}/pages/{page_number}/suggestions",
    status_code=204,
)
def clear_pending_page_suggestions(
    document_id: uuid.UUID,
    page_number: int,
    db: Session = Depends(get_db),
) -> None:
    doc = get_document_in_current_mode(db, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    resolve_page_range(page_number, page_number, doc.page_count)
    db.execute(
        delete(Suggestion).where(
            Suggestion.document_id == document_id,
            Suggestion.page == page_number,
            Suggestion.status.notin_(("applied", "rejected")),
        )
    )
    db.commit()


@router.post("/documents/{document_id}/analyze")
def analyze_stream(
    document_id: uuid.UUID,
    request: Request,
    preparation_context: bool = Query(
        default=False,
        description="Utiliser le mapping indépendant de l'étape Préparation.",
    ),
    vision: Optional[bool] = Query(
        default=None,
        description=(
            "Override per-run multimodal vision opt-in/out. None = use the "
            "persisted `vision.enabled` setting from /settings/mistral."
        ),
    ),
    checklist: bool = Query(
        default=True,
        description="Cible checklist : quand false, exclut les regles importees (llm_nl/manual) du run.",
    ),
    first_page: int = Query(default=1, ge=1, description="Premiere page physique a analyser."),
    last_page: Optional[int] = Query(
        default=None,
        ge=1,
        description="Derniere page physique a analyser. Par defaut : derniere page du document.",
    ),
    modified_only: bool = Query(
        default=False,
        description="N'analyser que les pages marquees comme modifiees ou indeterminees.",
    ),
    page_number: Optional[int] = Query(
        default=None,
        ge=1,
        description="Relancer une seule page apres correction manuelle de son statut.",
    ),
    additional_pages: list[int] | None = Query(
        default=None,
        description="Pages manuellement modifiees a ajouter au perimetre precedent.",
    ),
    page_overrides: Optional[str] = Query(
        default=None,
        description="JSON des statuts de page corriges manuellement, indexe par numero physique.",
    ),
    previous_revision_file: UploadFile | None = File(
        default=None,
        description="PDF optionnel du CMM de revision N-1 pour les controles comparatifs.",
    ),
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    doc = get_document_in_current_mode(db, document_id)
    if doc is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document introuvable", status_code=404)
    previous_revision_bytes: bytes | None = None
    if previous_revision_file is not None:
        if doc.working_format != "pdf":
            raise AppError(
                "PREVIOUS_REVISION_UNSUPPORTED",
                "La comparaison avec le CMM N-1 est disponible uniquement pour les PDF.",
                status_code=422,
            )
        filename = previous_revision_file.filename or ""
        if Path(filename).suffix.lower() != ".pdf":
            raise AppError(
                "PREVIOUS_REVISION_BAD_FORMAT",
                "Le CMM N-1 doit être fourni au format PDF.",
                status_code=400,
            )
        previous_revision_bytes = read_upload_bounded(
            previous_revision_file,
            settings.max_upload_size_bytes,
        )
        try:
            with fitz.open(stream=previous_revision_bytes, filetype="pdf") as previous_pdf:
                previous_page_count = previous_pdf.page_count
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                "PREVIOUS_REVISION_INVALID_PDF",
                "Le PDF du CMM N-1 est illisible.",
                status_code=400,
            ) from exc
        if previous_page_count < 1:
            raise AppError(
                "PREVIOUS_REVISION_INVALID_PDF",
                "Le PDF du CMM N-1 ne contient aucune page.",
                status_code=400,
            )
    previous_revision_sha256 = (
        hashlib.sha256(previous_revision_bytes).hexdigest()
        if previous_revision_bytes is not None
        else None
    )
    client_configuration = get_request_client_configuration(request, db)
    client_bundle = client_configuration.bundle
    analysis_metadata = dict(doc.client_metadata or {})
    preparation_page_classification: dict[str, dict[str, str | None]] = {}
    preparation_record: DocumentPreparation | None = None
    if preparation_context:
        if (
            doc.working_format != "pdf"
            or client_configuration.manifest.client_code != "THALES"
        ):
            raise AppError(
                "PREPARATION_CONTEXT_UNSUPPORTED",
                "Le mapping de préparation est réservé aux PDF THALES.",
                status_code=422,
            )
        preparation_record = db.scalar(
            select(DocumentPreparation).where(
                DocumentPreparation.document_id == document_id
            )
        )
        if preparation_record is None:
            raise AppError(
                "PREPARATION_CONTEXT_MISSING",
                "L'état de préparation de ce document est indisponible.",
                status_code=409,
            )
        saved_preparation_mapping = load_preparation_mapping(preparation_record)
        preparation_page_classification = load_page_classification(preparation_record)
        analysis_metadata = {
            name: saved_preparation_mapping[name]
            for name in client_configuration.mapping.fields
            if name in saved_preparation_mapping
        }
        validate_client_metadata_patch(
            analysis_metadata,
            client_configuration.mapping.fields,
        )
        for name, definition in client_configuration.mapping.fields.items():
            analysis_metadata.setdefault(name, definition.default)
    previous_run = db.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.document_id == document_id, AnalysisRun.status == "done")
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    )
    previous_bundle_hash: str | None = None
    if previous_run is not None:
        try:
            previous_snapshot = json.loads(previous_run.context_snapshot_json or "{}")
            previous_bundle_hash = previous_snapshot.get("client_bundle", {}).get("bundle_hash")
        except (AttributeError, TypeError, ValueError):
            previous_bundle_hash = None
    bundle_changed_since_previous_run = (
        previous_bundle_hash is not None
        and previous_bundle_hash != client_configuration.bundle_hash
    )
    missing_context = missing_document_context(
        doc,
        client_configuration.mapping,
        metadata_override=analysis_metadata if preparation_context else None,
    )
    if missing_context:
        raise AppError(
            "DOCUMENT_CONTEXT_INCOMPLETE",
            "Renseignez le contexte du document avant de lancer l'analyse.",
            detail={"fields": missing_context},
            status_code=409,
        )
    parsed_page_overrides = _parse_page_overrides(page_overrides, doc.page_count)
    additional_page_numbers = additional_pages or []
    if page_number is not None and additional_page_numbers:
        raise AppError(
            "PAGE_OVERRIDE_INVALID",
            "Une relance d'une seule page ne peut pas inclure de pages supplementaires.",
            status_code=422,
        )
    if len(set(additional_page_numbers)) != len(additional_page_numbers):
        raise AppError(
            "PAGE_OVERRIDE_INVALID",
            "La liste des pages supplementaires contient des doublons.",
            status_code=422,
        )
    for requested_page in additional_page_numbers:
        resolve_page_range(requested_page, requested_page, doc.page_count)
        if parsed_page_overrides.get(requested_page) is not True:
            raise AppError(
                "PAGE_OVERRIDE_INVALID",
                "Chaque page supplementaire doit etre marquee comme modifiee.",
                status_code=422,
            )
    if page_number is not None:
        resolve_page_range(page_number, page_number, doc.page_count)
        if page_number not in parsed_page_overrides:
            raise AppError(
                "PAGE_OVERRIDE_INVALID",
                "Le statut manuel de la page a corriger est absent.",
                status_code=422,
            )
        resolved_first_page, resolved_last_page = page_number, page_number
    else:
        resolved_first_page, resolved_last_page = resolve_page_range(
            first_page,
            last_page,
            doc.page_count,
        )
    partial_page_range = (
        page_number is not None
        or (
            not modified_only
            and any(
                page < resolved_first_page or page > resolved_last_page
                for page in additional_page_numbers
            )
        )
        or resolved_first_page != 1
        or resolved_last_page != doc.page_count
    )
    _logger.info(
        "analysis_requested",
        source_format=doc.source_format,
        working_format=doc.working_format,
        page_count=doc.page_count,
        first_page=resolved_first_page,
        last_page=resolved_last_page,
        modified_only=modified_only,
        page_number=page_number,
        additional_pages=additional_page_numbers,
        checklist_enabled=checklist,
        vision_override=vision,
    )

    # Run on the current version (post-edit) so the user can re-run the
    # analysis after applying suggestions and pick up new issues that the
    # edit may have introduced (or simply check that fixes hold). Le chemin
    # depend du pipeline : .pdf (defaut) ou .docx (pipeline Word natif).
    is_docx = doc.working_format == "docx"
    if is_docx:
        from app.core import docx_versioning

        src = docx_versioning.version_path(doc.storage_dir, doc.current_version)
        if not src.is_file():
            raise AppError("DOCX_VERSION_MISSING", "DOCX courant absent", status_code=500)
    else:
        src = current_path(doc.storage_dir, doc.current_version)
        if not src.is_file():
            raise AppError("PDF_VERSION_MISSING", "PDF courant absent", status_code=500)

    # Rejection memory (corpus-agent-style): capture the signatures of every
    # finding the reviewer previously *rejected* on THIS document, so the same
    # false positive is not re-surfaced on re-analysis. Signature = (rule_code,
    # original_text) — the verbatim span text is exact enough on a PDF. Empty
    # original_text (absence-type findings) can't be matched reliably → skipped.
    from sqlalchemy import delete
    from sqlalchemy import select as _select

    rejected_rows = db.execute(
        _select(Suggestion.rule_code, Suggestion.original_text).where(
            Suggestion.document_id == document_id,
            Suggestion.status == "rejected",
        )
    ).all()
    rejected_sigs: set[tuple[str, str]] = {(rc, ot) for rc, ot in rejected_rows if ot}

    # Drop transient suggestions from prior runs but PRESERVE the ones already
    # applied (undo needs the row) AND the ones rejected (they feed the memory
    # above and must persist their motif). Open / edited / accepted are
    # superseded by the fresh run so we wipe them.
    if page_number is None:
        db.execute(
            delete(Suggestion).where(
                Suggestion.document_id == document_id,
                Suggestion.status.notin_(("applied", "rejected")),
            )
        )
    sv_id = doc.standard_version_id
    # v2 multi-norm: parse the JSON list, fall back to the legacy single FK.
    try:
        sv_ids_list = json.loads(doc.standard_version_ids or "[]")
        if not isinstance(sv_ids_list, list):
            sv_ids_list = []
    except (ValueError, TypeError):
        sv_ids_list = []
    sv_ids_list = analysis_standard_version_ids(
        request,
        db,
        sv_ids_list,
        sv_id,
    )
    if preparation_context:
        active_catalog_ids = [
            str(version.id)
            for version in active_standard_versions(db, client_configuration)
        ]
        sv_ids_list = list(dict.fromkeys([*active_catalog_ids, *sv_ids_list]))
    if sv_ids_list and (sv_id is None or str(sv_id) not in sv_ids_list):
        try:
            sv_id = uuid.UUID(str(sv_ids_list[0]))
        except (ValueError, TypeError):
            pass
    analysis_meta_fields = {
        "meta_revision_date": (
            analysis_metadata.get("meta_revision_date")
            if preparation_context
            else doc.meta_revision_date
        ),
        "meta_cmm_number": (
            analysis_metadata.get("meta_cmm_number")
            if preparation_context
            else doc.meta_cmm_number
        ),
        "meta_first_issue_date": (
            analysis_metadata.get("meta_first_issue_date")
            if preparation_context
            else doc.meta_first_issue_date
        ),
        "meta_last_issue_date": (
            analysis_metadata.get("meta_last_issue_date")
            if preparation_context
            else doc.meta_last_issue_date
        ),
        "meta_revision_number": (
            analysis_metadata.get("meta_revision_number")
            if preparation_context
            else doc.meta_revision_number
        ),
        "meta_pnr_number": (
            analysis_metadata.get("meta_pnr_number")
            if preparation_context
            else doc.meta_pnr_number
        ),
        "meta_manufacturer": (
            analysis_metadata.get("meta_manufacturer")
            if preparation_context
            else doc.meta_manufacturer
        ),
        "document_language": (
            analysis_metadata.get("document_language")
            if preparation_context
            else doc.document_language
        ),
    }
    context_snapshot = json.dumps(
        {
            "client_bundle": {
                "bundle": client_configuration.selection.bundle,
                "rule_bundles": client_configuration.selection.rule_bundles,
                "client_code": client_configuration.manifest.client_code,
                "bundle_version": client_configuration.manifest.bundle_version,
                "contract_version": client_configuration.manifest.contract_version,
                "catalogs": [
                    catalog.model_dump(mode="json")
                    for catalog in client_configuration.bundle.catalogs
                ],
                "manifest_hash": client_configuration.manifest_hash,
                "mapping_hash": client_configuration.mapping_hash,
                "bundle_hash": client_configuration.bundle_hash,
                "reanalysis": {
                    "previous_bundle_hash": previous_bundle_hash,
                    "using_current_bundle": bundle_changed_since_previous_run,
                },
            },
            "analysis_scope": {
                "first_page": resolved_first_page,
                "last_page": resolved_last_page,
                "modified_only": modified_only,
                "page_number": page_number,
                "page_overrides": parsed_page_overrides,
            },
            "previous_revision": (
                {"sha256": previous_revision_sha256}
                if previous_revision_sha256 is not None
                else None
            ),
            "metadata": {
                "source": "preparation" if preparation_context else "verification",
                "client_metadata": analysis_metadata,
                **analysis_meta_fields,
            },
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    run = AnalysisRun(
        document_id=document_id,
        standard_version_id=sv_id,
        standard_version_ids=json.dumps(sv_ids_list),
        status="running",
        context_snapshot_json=context_snapshot,
        compiled_rules_snapshot_json="[]",
        snapshot_sha256=hashlib.sha256(context_snapshot.encode("utf-8")).hexdigest(),
    )
    db.add(run)
    # Mark the document as analyzing immediately so the UI list reflects
    # the in-progress state (poll-driven badge update).
    doc.status = "analyzing"
    db.commit()
    db.refresh(run)

    document_id_value = document_id
    run_id_value = run.id
    src_path = str(src)
    previous_revision_bytes_value = previous_revision_bytes
    target_unit = doc.target_unit_system
    # Portail qualite : etat de revuabilite (homogene tous formats), signale en
    # tete de flux pour qu'un document non exploitable (scan sans couche texte)
    # ne rende pas une revue vide silencieuse.
    quality_value = doc.quality
    coverage_value = doc.text_coverage
    convert_engine_value = doc.convert_engine
    sv_ids_value = sv_ids_list
    vision_override_value = vision  # captured for the worker thread
    checklist_enabled_value = checklist  # captured for the worker thread
    rejected_sigs_value = rejected_sigs  # captured for the worker thread
    is_docx_value = is_docx  # pipeline Word natif vs PDF
    # Mapping manuel du document (cf. rules_engine._doc_meta_block) — capture
    # avant d'entrer dans le worker thread (pas de reutilisation de session ORM).
    meta_revision_date_value = analysis_meta_fields["meta_revision_date"]
    meta_cmm_number_value = analysis_meta_fields["meta_cmm_number"]
    meta_first_issue_date_value = analysis_meta_fields["meta_first_issue_date"]
    meta_last_issue_date_value = analysis_meta_fields["meta_last_issue_date"]
    meta_revision_number_value = analysis_meta_fields["meta_revision_number"]
    meta_pnr_number_value = analysis_meta_fields["meta_pnr_number"]
    meta_manufacturer_value = analysis_meta_fields["meta_manufacturer"]
    document_language_value = analysis_meta_fields["document_language"]
    client_metadata_value = analysis_metadata
    first_page_value = resolved_first_page
    last_page_value = resolved_last_page
    partial_page_range_value = partial_page_range
    doc_page_count_value = doc.page_count
    modified_only_value = modified_only
    page_number_value = page_number
    additional_pages_value = additional_page_numbers
    page_overrides_value = parsed_page_overrides

    async def event_gen():
        yield {
            "event": "run_started",
            "data": json.dumps({
                "run_id": str(run_id_value),
                "document_id": str(document_id_value),
                "first_page": first_page_value,
                "last_page": last_page_value,
            }),
        }
        yield {
            "event": "quality",
            "data": json.dumps({
                "state": quality_value,
                "coverage": coverage_value,
                "engine": convert_engine_value,
            }),
        }

        progress_q: "SimpleQueue[dict[str, object]]" = SimpleQueue()
        loop = asyncio.get_running_loop()
        parse_end_pct = 95
        main_parse_end_pct = 90 if previous_revision_bytes_value is not None else parse_end_pct

        def _queue_progress(payload: dict[str, object]) -> None:
            loop.call_soon_threadsafe(progress_q.put_nowait, payload)

        def _on_parse_progress(current_page: int, total_pages: int | None) -> None:
            if total_pages is None:
                _queue_progress({
                    "step": "parse",
                    "pct": 0,
                    "current": current_page,
                    "unit": "block",
                })
                return
            pct = round(main_parse_end_pct * current_page / max(total_pages, 1))
            _queue_progress({
                "step": "parse",
                "pct": pct,
                "current": current_page,
                "total": total_pages,
                "unit": "page",
            })

        def _on_previous_revision_progress(current_page: int, total_pages: int) -> None:
            pct = main_parse_end_pct + round(
                (parse_end_pct - main_parse_end_pct) * current_page / max(total_pages, 1)
            )
            _queue_progress({
                "step": "parse_previous",
                "pct": pct,
                "current": current_page,
                "total": total_pages,
                "unit": "page",
            })

        async def _progress_events_until_done(task):
            while not task.done():
                try:
                    payload = progress_q.get_nowait()
                except Empty:
                    await asyncio.sleep(0.2)
                else:
                    yield {"event": "progress", "data": json.dumps(payload)}
            await asyncio.sleep(0)
            while True:
                try:
                    payload = progress_q.get_nowait()
                except Empty:
                    break
                yield {"event": "progress", "data": json.dumps(payload)}

        try:
            yield {"event": "progress", "data": json.dumps({"step": "parse", "pct": 0})}
            if is_docx_value:
                from app.parsers.docx_parser import parse_docx

                parse_task = asyncio.create_task(
                    asyncio.to_thread(
                        lambda: parse_docx(src_path, progress_cb=_on_parse_progress)
                    )
                )
            else:
                parse_task = asyncio.create_task(
                    asyncio.to_thread(
                        lambda: parse_pdf(src_path, progress_cb=_on_parse_progress)
                    )
                )
            async for event in _progress_events_until_done(parse_task):
                yield event
            parsed = await parse_task
            if preparation_record is not None:
                apply_preparation_ocr(parsed, preparation_record)
            if is_docx_value:
                parsed = filter_docx(parsed, first_page_value, last_page_value)
            previous_parsed = None
            if previous_revision_bytes_value is not None:
                previous_parse_task = asyncio.create_task(
                    asyncio.to_thread(
                        lambda: parse_pdf(
                            previous_revision_bytes_value,
                            progress_cb=_on_previous_revision_progress,
                        )
                    )
                )
                async for event in _progress_events_until_done(previous_parse_task):
                    yield event
                previous_parsed = await previous_parse_task
            # `page.page_type` (le cas echeant) n'est peuple qu'une fois les
            # standards selectionnes connus : voir le classifieur invoque par
            # `rules_engine.run_all` plus bas, jamais ici (pipeline generique).
            page_types: dict[str, str | None] = {}
            if is_docx_value:
                parsed_page_count = parsed.block_count
                parsed_text_chars = sum(len(block.text or "") for block in parsed.blocks)
                span_count = 0
            else:
                parsed_page_count = len(parsed.pages)
                parsed_text_chars = sum(len(page.text or "") for page in parsed.pages)
                span_count = sum(len(page.spans) for page in parsed.pages)
            _logger.info(
                "analysis_document_parsed",
                format="docx" if is_docx_value else "pdf",
                page_count=parsed_page_count,
                text_chars=parsed_text_chars,
                span_count=span_count,
            )
            yield {"event": "progress", "data": json.dumps({"step": "rules", "pct": 95})}

            # Build a lightweight Document-like with target_unit_system (we
            # don't reuse the ORM session inside the worker thread).
            class _DocStub:
                target_unit_system = target_unit
                meta_revision_date = meta_revision_date_value
                meta_cmm_number = meta_cmm_number_value
                meta_first_issue_date = meta_first_issue_date_value
                meta_last_issue_date = meta_last_issue_date_value
                meta_revision_number = meta_revision_number_value
                meta_pnr_number = meta_pnr_number_value
                meta_manufacturer = meta_manufacturer_value
                document_language = document_language_value
                client_metadata = client_metadata_value

            scoped_session: Session = SessionLocal()
            try:
                versions: list = []
                for raw_id in sv_ids_value:
                    try:
                        vid = uuid.UUID(str(raw_id))
                    except (ValueError, TypeError):
                        continue
                    sv = scoped_session.get(StandardVersion, vid)
                    if sv is not None:
                        versions.append(sv)

                selected_page_numbers: list[int] = []
                page_status_payload: list[dict[str, object]] = []
                full_page_count = parsed.page_count if not is_docx_value else doc_page_count_value
                if not is_docx_value:
                    page_classifier = client_bundle.page_classifier
                    if page_classifier is not None:
                        for version in versions:
                            if version.standard.code in client_bundle.standard_specs:
                                page_classifier(parsed, _DocStub())
                    if preparation_context:
                        from app.checks.thales_rules.section_detection import (
                            apply_preparation_page_types,
                        )

                        apply_preparation_page_types(
                            parsed,
                            client_metadata_value,
                            preparation_page_classification,
                        )
                    revision_state = getattr(parsed, "_thales_revision_state", None)
                    has_revision_evidence = revision_state is not None and bool(
                        getattr(revision_state, "highlights_pages", ())
                        or getattr(revision_state, "lep_pages", ())
                    )
                    for page in parsed.pages:
                        if page.page in page_overrides_value:
                            page.is_modified = page_overrides_value[page.page]
                    page_status_payload = [
                        {
                            "page": page.page,
                            "is_modified": page.is_modified,
                            "source": "manual" if page.page in page_overrides_value else "detected",
                            "requires_review": (
                                has_revision_evidence and page.is_modified is None
                            ),
                        }
                        for page in parsed.pages
                    ]
                    yield {
                        "event": "page_statuses",
                        "data": json.dumps({"pages": page_status_payload}),
                    }
                    selected_page_numbers = select_pdf_page_numbers(
                        parsed,
                        first_page=first_page_value,
                        last_page=None if modified_only_value or page_number_value is not None else last_page_value,
                        modified_only=modified_only_value,
                        page_number=page_number_value,
                        additional_pages=additional_pages_value,
                        include_undecided=not has_revision_evidence,
                    )
                    cached_revision_state = getattr(parsed, "_thales_revision_state", None)
                    parsed = filter_pdf_pages(parsed, selected_page_numbers)
                    if cached_revision_state is not None:
                        setattr(parsed, "_thales_revision_state", cached_revision_state)
                else:
                    selected_page_numbers = sorted({block.page for block in parsed.blocks})
                partial_analysis_value = (
                    partial_page_range_value
                    if is_docx_value
                    else selected_page_numbers != list(range(1, full_page_count + 1))
                )

                if page_number_value is not None:
                    scoped_session.execute(
                        delete(Suggestion).where(
                            Suggestion.document_id == document_id_value,
                            Suggestion.page == page_number_value,
                            Suggestion.status.notin_(("applied", "rejected")),
                        )
                    )
                    scoped_session.commit()

                run_row = scoped_session.get(AnalysisRun, run_id_value)
                if run_row is not None:
                    try:
                        context_payload = json.loads(run_row.context_snapshot_json or "{}")
                    except (TypeError, ValueError):
                        context_payload = {}
                    context_payload["analysis_scope"] = {
                        "first_page": first_page_value,
                        "last_page": last_page_value,
                        "modified_only": modified_only_value,
                        "page_number": page_number_value,
                        "additional_pages": additional_pages_value,
                        "selected_pages": selected_page_numbers,
                        "page_overrides": page_overrides_value,
                    }
                    context_payload["page_statuses"] = page_status_payload
                    run_row.context_snapshot_json = json.dumps(
                        context_payload,
                        ensure_ascii=True,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    scoped_session.commit()

                # Le scan checklist/IA (une passe Mistral par page) domine
                # generalement le temps d'une analyse : sans remontee de
                # progression pendant ce calcul (execute dans un thread), la
                # jauge restait figee puis sautait directement a la fin,
                # donnant l'impression qu'elle "disparaissait". `progress_q`
                # relie le callback (appele depuis le thread) au generateur
                # SSE (event loop) via `call_soon_threadsafe`.
                def _on_progress(pct: int) -> None:
                    normalized_pct = min(max(pct, 35), 65)
                    rules_pct = 95 + round((normalized_pct - 35) * 2 / 30)
                    _queue_progress({"step": "rules", "pct": rules_pct})

                # Echecs du scan checklist/IA (Mistral mal configure, quota,
                # modele invalide sur un endpoint prive…) : remontes ici au
                # lieu de se traduire silencieusement par "0 anomalie" (HR7).
                run_warnings: list[str] = []
                compiled_results = []
                if bundle_changed_since_previous_run:
                    run_warnings.append(
                        "Le run precedent utilisait un autre bundle; cette analyse "
                        f"utilise le bundle actif {client_configuration.manifest.client_code} "
                        f"v{client_configuration.manifest.bundle_version}."
                    )
                if modified_only_value and not selected_page_numbers and page_number_value is None:
                    run_warnings.append("Aucune page modifiee detectee; aucune regle n'a ete executee.")
                if partial_analysis_value and vision_override_value:
                    run_warnings.append(
                        "Analyse vision ignoree pour une plage partielle de pages"
                    )

                if is_docx_value:
                    from app.core import docx_pipeline

                    task = asyncio.create_task(
                        asyncio.to_thread(
                            lambda: docx_pipeline.run_docx(
                                parsed, _DocStub(), scoped_session, versions,  # type: ignore[arg-type]
                                checklist_enabled=checklist_enabled_value,
                                progress_cb=_on_progress,
                                warnings=run_warnings,
                                compiled_results=compiled_results,
                                client_bundle=client_bundle,
                            )
                        )
                    )
                    async for event in _progress_events_until_done(task):
                        yield event
                    raws = await task
                    yield {"event": "progress", "data": json.dumps({"step": "finalize", "pct": 97})}
                    rows = docx_pipeline.materialize_docx(
                        raws, parsed, document_id_value, run_id_value
                    )
                else:
                    if parsed.pages:
                        task = asyncio.create_task(
                            asyncio.to_thread(
                                lambda: run_all(
                                    parsed, _DocStub(), scoped_session, versions,  # type: ignore[arg-type]
                                    src_path=src_path if not partial_analysis_value else None,
                                    vision_enabled_override=(
                                        vision_override_value
                                        if not partial_analysis_value
                                        else False
                                    ),
                                    checklist_enabled=checklist_enabled_value,
                                    progress_cb=_on_progress,
                                    warnings=run_warnings,
                                    compiled_results=compiled_results,
                                    client_bundle=client_bundle,
                                    previous_revision_pdf=previous_parsed,
                                )
                            )
                        )
                        async for event in _progress_events_until_done(task):
                            yield event
                        raws = await task
                    else:
                        raws = []
                    yield {"event": "progress", "data": json.dumps({"step": "finalize", "pct": 97})}
                    rows = materialize(raws, parsed, document_id_value, run_id_value, src_path=src_path)
                    rows = [row for row in rows if row.page in set(selected_page_numbers)]
                    # A ce stade, le classifieur du ClientBundle invoque par
                    # `run_all` a pu peupler `page.page_type`; on le capture ici.
                    page_types = {str(page.page): page.page_type for page in parsed.pages}

                run_row = scoped_session.get(AnalysisRun, run_id_value)
                if run_row is not None:
                    try:
                        context_payload = json.loads(run_row.context_snapshot_json or "{}")
                    except (TypeError, ValueError):
                        context_payload = {}
                    context_payload["page_types"] = page_types
                    run_row.context_snapshot_json = json.dumps(
                        context_payload,
                        ensure_ascii=True,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    scoped_session.commit()

                if run_warnings:
                    yield {"event": "warning", "data": json.dumps({"messages": run_warnings})}

                total = 0
                suppressed_rejected = 0
                total_rows = len(rows)
                for row_index, sug in enumerate(rows, start=1):
                    # Rejection memory: suppress a re-detection the reviewer
                    # already rejected on this document (same rule_code + text).
                    if (sug.rule_code, sug.original_text) in rejected_sigs_value:
                        suppressed_rejected += 1
                    else:
                        scoped_session.add(sug)
                        scoped_session.commit()
                        scoped_session.refresh(sug)
                        payload = SuggestionOut.model_validate(sug).model_dump(mode="json")
                        yield {"event": "suggestion", "data": json.dumps(payload)}
                        total += 1
                    if total_rows:
                        yield {
                            "event": "progress",
                            "data": json.dumps({
                                "step": "suggestions",
                                "pct": 97 + int(2 * row_index / total_rows),
                                "current": row_index,
                                "total": total_rows,
                            }),
                        }

                run_row = scoped_session.get(AnalysisRun, run_id_value)
                if run_row is not None:
                    compiled_rules = load_compiled_rules(
                        scoped_session,
                        versions,
                        checklist_enabled=checklist_enabled_value,
                    )
                    compiled_snapshot = json.dumps(
                        {
                            "rules": [rule.model_dump(mode="json") for rule in compiled_rules],
                            "results": [result.model_dump(mode="json") for result in compiled_results],
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    run_row.status = "done"
                    run_row.finished_at = datetime.now(timezone.utc)
                    run_row.compiled_rules_snapshot_json = compiled_snapshot
                    run_row.snapshot_sha256 = hashlib.sha256(
                        f"{run_row.context_snapshot_json}\n{compiled_snapshot}".encode("utf-8")
                    ).hexdigest()
                    run_row.summary = json.dumps(
                        {"total": total, "suppressed_rejected": suppressed_rejected}
                    )
                    scoped_session.commit()

                doc_row = scoped_session.get(Document, document_id_value)
                if doc_row is not None:
                    doc_row.status = "analyzed"
                    scoped_session.commit()

                _logger.info(
                    "analysis_finished",
                    total_suggestions=total,
                    suppressed_rejected=suppressed_rejected,
                    warning_count=len(run_warnings),
                    compiled_result_count=len(compiled_results),
                )
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "total": total,
                        "suppressed_rejected": suppressed_rejected,
                        "run_id": str(run_id_value),
                    }),
                }
            finally:
                scoped_session.close()
        except AppError as exc:
            _logger.warning(
                "analysis_failed",
                error=exc.code,
            )
            _mark_failed(document_id_value)
            yield {"event": "error", "data": json.dumps({"code": exc.code, "message": exc.message})}
        except Exception as exc:  # noqa: BLE001
            _logger.error(
                "analysis_failed",
                error=type(exc).__name__,
            )
            _mark_failed(document_id_value)
            yield {
                "event": "error",
                "data": json.dumps({"code": "INTERNAL_ERROR", "message": "Erreur interne pendant l'analyse."}),
            }

    return EventSourceResponse(event_gen())


def _mark_failed(document_id: uuid.UUID) -> None:
    """Reset Document.status if the analyse run blew up — never leave a
    document stuck in `analyzing` for the UI poller."""
    s = SessionLocal()
    try:
        doc = s.get(Document, document_id)
        if doc is not None and doc.status == "analyzing":
            doc.status = "analysis_failed"
            s.commit()
    except Exception:  # noqa: BLE001
        s.rollback()
    finally:
        s.close()
