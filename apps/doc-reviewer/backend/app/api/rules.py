"""Rules CRUD — user-defined regex rules used during analyze."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, desc, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.checks.client_registry import active_standard_versions
from app.config import settings
from app.core import ingest
from app.core.checklist_compiler import compile_checklist_rule
from app.core.compiled_rule_store import persist_compiled_rule
from app.core.compiled_rules import describe_compiled_rule, validate_compiled_rule_json
from app.core.standard_rule_compiler import compile_standard_rule
from app.core.errors import AppError
from app.core.excel_rules import list_sheets, parse_checklist
from app.core.llm_suggester import suggest_rules_from_corpus
from app.core.pdf_versioning import current_path
from app.core.rules_engine import validate_rule_pattern
from app.core.security import read_upload_limited
from app.db.models import CompiledRuleVersion, Document, Rule, StandardVersion
from app.db.session import get_db
from app.parsers.pdf_parser import parse_pdf
from app.schemas import (
    RuleImportResult,
    CompiledRuleSummary,
    CompiledRulePatchIn,
    RuleIn,
    RuleOut,
    RulePatchIn,
    RuleSuggestIn,
    RuleSuggestionItem,
    RuleSuggestOut,
    SheetInfo,
    SheetInspectOut,
    ClientCatalogOut,
    ClientConfigOut,
    ClientRuleOut,
    ClientRulePatchIn,
)

# Kinds produits par l'import checklist (langage naturel juge par le LLM +
# verification humaine). Servent de perimetre aux modes replace / validate-all.
_CHECKLIST_KINDS = ("llm_nl", "manual")
_CHECKLIST_TEMPLATE = Path(__file__).resolve().parent.parent / "static" / "checklist_template.xlsx"

logger = structlog.get_logger(__name__)


_SUGGEST_MAX_DOCS = 20  # never sample more than this
_SUGGEST_PER_DOC_BUDGET = 6_000  # chars kept per document before the LLM call (H-04)


def _truncate_sample(text: str, limit: int) -> tuple[str, bool]:
    """Cap `text` to `limit` chars at a whitespace boundary (never mid-word)
    and mark the cut explicitly in the returned text (H-04 hardening: a real
    multi-page PDF easily exceeds the total request budget when sent whole;
    per-document truncation keeps the feature usable, and the explicit
    `[...]` marker — plus `documents_truncated` in the response — means the
    cut is visible instead of silent)."""
    if len(text) <= limit:
        return text, False
    cut = text.rfind(" ", 0, limit)
    if cut <= 0:
        cut = limit
    return text[:cut].rstrip() + " [...]", True


router = APIRouter(tags=["rules"])


def _client_rule_catalog(
    client_bundle: Any,
    rule_code: str,
) -> tuple[str, str] | None:
    for catalog in client_bundle.catalogs:
        spec = client_bundle.standard_specs.get(catalog.code)
        versions = spec.get("versions") if spec is not None else None
        rules = versions.get(catalog.version, []) if isinstance(versions, dict) else []
        if any(getattr(rule, "id", None) == rule_code for rule in rules):
            return catalog.code, catalog.version
    return None


def _client_rule_statuses(request: Request, db: Session) -> dict[tuple[str, str], set[str]]:
    configuration = request.app.state.client_configuration
    versions = active_standard_versions(db, configuration)
    disabled_by_catalog: dict[tuple[str, str], set[str]] = {}
    for version in versions:
        try:
            disabled = json.loads(version.disabled_rule_codes or "[]")
        except (TypeError, ValueError):
            disabled = []
        disabled_by_catalog[(version.standard.code, version.label)] = {
            str(code) for code in disabled if str(code).strip()
        } if isinstance(disabled, list) else set()
    return disabled_by_catalog


@router.get("/client-config", response_model=ClientConfigOut)
def get_client_config(
    request: Request,
    db: Session = Depends(get_db),
) -> ClientConfigOut:
    configuration = request.app.state.client_configuration
    versions = active_standard_versions(db, configuration)
    version_ids = {
        (version.standard.code, version.label): version.id
        for version in versions
    }
    return ClientConfigOut(
        client_code=configuration.manifest.client_code,
        label=configuration.manifest.label,
        bundle=configuration.selection.bundle,
        bundle_version=configuration.manifest.bundle_version,
        contract_version=configuration.manifest.contract_version,
        manifest_hash=configuration.manifest_hash,
        mapping_hash=configuration.mapping_hash,
        bundle_hash=configuration.bundle_hash,
        catalogs=[
            ClientCatalogOut(
                code=catalog.code,
                version=catalog.version,
                standard_version_id=version_ids[(catalog.code, catalog.version)],
            )
            for catalog in configuration.manifest.catalogs
        ],
        mapping=configuration.mapping.model_dump(mode="json"),
        ui_options=configuration.manifest.ui_options,
    )


@router.get("/client-rules", response_model=list[ClientRuleOut])
def list_client_rules(
    request: Request,
    db: Session = Depends(get_db),
) -> list[ClientRuleOut]:
    configuration = request.app.state.client_configuration
    disabled_by_catalog = _client_rule_statuses(request, db)
    results: list[ClientRuleOut] = []
    for definition in configuration.bundle.rules:
        catalog = _client_rule_catalog(configuration.bundle, definition.code)
        if catalog is None:
            continue
        disabled = disabled_by_catalog.get(catalog, set())
        compiled = definition.compiled_rule
        results.append(
            ClientRuleOut(
                code=definition.code,
                name=definition.name,
                description=definition.description,
                message=definition.message,
                kind=definition.kind,
                severity=definition.presentation_severity or compiled.severity,
                execution=compiled.execution,
                active=definition.code not in disabled,
                catalog_code=catalog[0],
                catalog_version=catalog[1],
                translations=definition.translations,
            )
        )
    return results


@router.patch("/client-rules/{rule_code}", response_model=ClientRuleOut)
def patch_client_rule(
    rule_code: str,
    body: ClientRulePatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> ClientRuleOut:
    configuration = request.app.state.client_configuration
    definition = next(
        (item for item in configuration.bundle.rules if item.code == rule_code),
        None,
    )
    catalog = _client_rule_catalog(configuration.bundle, rule_code)
    if definition is None or catalog is None:
        raise AppError("CLIENT_RULE_NOT_FOUND", "Règle client introuvable", status_code=404)
    version = next(
        (
            item
            for item in active_standard_versions(db, configuration)
            if (item.standard.code, item.label) == catalog
        ),
        None,
    )
    if version is None:
        raise AppError("CLIENT_CATALOG_NOT_FOUND", "Catalogue client introuvable", status_code=404)
    try:
        disabled = set(json.loads(version.disabled_rule_codes or "[]"))
    except (TypeError, ValueError):
        disabled = set()
    if body.active:
        disabled.discard(rule_code)
    else:
        disabled.add(rule_code)
    version.disabled_rule_codes = json.dumps(sorted(disabled), ensure_ascii=False)
    db.commit()
    db.refresh(version)
    compiled = definition.compiled_rule
    return ClientRuleOut(
        code=definition.code,
        name=definition.name,
        description=definition.description,
        message=definition.message,
        kind=definition.kind,
        severity=definition.presentation_severity or compiled.severity,
        execution=compiled.execution,
        active=body.active,
        catalog_code=catalog[0],
        catalog_version=catalog[1],
        translations=definition.translations,
    )


@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    standard_version_id: Optional[uuid.UUID] = Query(default=None),
    include_transverse: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[Rule]:
    """List rules.

    - No filter → every rule.
    - `standard_version_id=<id>` → rules scoped to that version, plus
      transverse rules (no standard_version_id) when `include_transverse`.
    - `standard_version_id=<id>&include_transverse=false` → strictly scoped.
    """
    stmt = select(Rule)
    if standard_version_id is not None:
        if include_transverse:
            stmt = stmt.where(
                or_(
                    Rule.standard_version_id == standard_version_id,
                    Rule.standard_version_id.is_(None),
                )
            )
        else:
            stmt = stmt.where(Rule.standard_version_id == standard_version_id)
    return list(db.scalars(stmt.order_by(Rule.created_at.desc())))


def _validate_standard_version(sv_id: Optional[uuid.UUID], db: Session) -> None:
    if sv_id is None:
        return
    if db.get(StandardVersion, sv_id) is None:
        raise AppError(
            "STANDARD_VERSION_NOT_FOUND",
            "Version de norme introuvable",
            status_code=400,
        )


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(body: RuleIn, db: Session = Depends(get_db)) -> Rule:
    validate_rule_pattern(body.pattern)
    _validate_standard_version(body.standard_version_id, db)
    rule = Rule(
        name=body.name,
        kind=body.kind,
        pattern=body.pattern,
        replacement=body.replacement,
        severity=body.severity,
        message=body.message,
        enabled=body.enabled,
        standard_version_id=body.standard_version_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=RuleOut)
def patch_rule(rule_id: uuid.UUID, body: RulePatchIn, db: Session = Depends(get_db)) -> Rule:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise AppError("RULE_NOT_FOUND", "Règle introuvable", status_code=404)
    if body.pattern is not None:
        validate_rule_pattern(body.pattern)
        rule.pattern = body.pattern
    if body.standard_version_id is not None:
        _validate_standard_version(body.standard_version_id, db)
        rule.standard_version_id = body.standard_version_id
    for field in ("name", "kind", "replacement", "severity", "message", "enabled"):
        value = getattr(body, field)
        if value is not None:
            setattr(rule, field, value)
    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise AppError("RULE_NOT_FOUND", "Règle introuvable", status_code=404)
    db.delete(rule)
    db.commit()


@router.post("/rules/suggest", response_model=RuleSuggestOut)
def suggest_rules(
    body: RuleSuggestIn | None = None,
    db: Session = Depends(get_db),
) -> RuleSuggestOut:
    """Ask Mistral to propose new editorial rules from already-uploaded PDFs.

    `body.document_ids` restricts the corpus; empty / missing means every
    document with extractable text. `body.standard_version_id` tailors the
    prompt to a specific norm (injects the existing catalog so the LLM
    doesn't duplicate built-in rules; returned suggestions carry that
    `standard_version_id` so the UI can apply them scoped to the norm).
    Suggestions are returned in-memory — they are NOT persisted; the UI
    applies the user-selected ones via the regular `POST /rules` endpoint.
    """
    import json as _json

    from app.db.models import StandardVersion

    body = body or RuleSuggestIn()
    standard_context: dict | None = None
    if body.standard_version_id is not None:
        sv = db.get(StandardVersion, body.standard_version_id)
        if sv is None:
            raise AppError(
                "STANDARD_VERSION_NOT_FOUND",
                "Version de norme introuvable",
                status_code=400,
            )
        try:
            catalog = _json.loads(sv.catalog_json or "[]")
        except _json.JSONDecodeError:
            catalog = []
        standard_context = {
            "code": sv.standard.code,
            "label": sv.standard.label,
            "description": sv.standard.description,
            "version_label": sv.label,
            "catalog": catalog if isinstance(catalog, list) else [],
        }

    stmt = select(Document)
    if body.document_ids:
        stmt = stmt.where(Document.id.in_(body.document_ids))
    documents = list(db.scalars(stmt.order_by(Document.created_at.desc())))
    if not documents:
        raise AppError(
            "NO_DOCS_FOR_SUGGESTIONS",
            "Aucun document dans le périmètre — uploade d'abord des PDFs.",
            status_code=400,
        )
    if len(documents) > _SUGGEST_MAX_DOCS:
        raise AppError(
            "RULE_SUGGEST_TOO_MANY_DOCUMENTS",
            f"Sélectionnez au plus {_SUGGEST_MAX_DOCS} documents; aucun document n'a été ignoré.",
            status_code=413,
        )

    samples: list[str] = []
    docs_analyzed = 0
    docs_truncated = 0
    for doc in documents:
        try:
            pdf_path = current_path(doc.storage_dir, doc.current_version)
            parsed = parse_pdf(pdf_path)
        except Exception as exc:
            logger.warning(
                "rule_suggest_doc_skipped",
                error=type(exc).__name__,
            )
            raise AppError(
                "RULE_SUGGEST_INPUT_INCOMPLETE",
                "Un document du périmètre n'a pas pu être analysé intégralement; aucune suggestion n'a été produite.",
                status_code=422,
            ) from exc
        text = (parsed.full_text or "").strip()
        if not text:
            raise AppError(
                "RULE_SUGGEST_INPUT_INCOMPLETE",
                "Un document du périmètre ne contient pas de texte analysable; aucune suggestion n'a été produite.",
                status_code=422,
            )
        snippet, was_truncated = _truncate_sample(text, _SUGGEST_PER_DOC_BUDGET)
        if was_truncated:
            docs_truncated += 1
        samples.append(f"=== {doc.original_filename} ===\n{snippet}")
        docs_analyzed += 1

    if not samples:
        raise AppError(
            "NO_TEXT_FOR_SUGGESTIONS",
            "Les documents du périmètre n'ont pas de texte exploitable. "
            "Re-upload un PDF avec une couche texte.",
            status_code=400,
        )

    try:
        items = suggest_rules_from_corpus(db, samples, standard_context=standard_context)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            "RULE_SUGGEST_FAILED",
            f"Mistral a échoué : {type(exc).__name__}: {exc}",
            status_code=502,
        ) from exc

    sv_id = body.standard_version_id
    return RuleSuggestOut(
        suggestions=[
            RuleSuggestionItem(**{**item, "standard_version_id": sv_id})
            for item in items
        ],
        documents_analyzed=docs_analyzed,
        documents_truncated=docs_truncated,
    )


# =============================================================================
# Import checklist Excel  (Topic | Check -> regles `llm_nl` jugees par le LLM)
# =============================================================================


@router.get("/rules/template")
def download_checklist_template() -> FileResponse:
    """Modele .xlsx de checklist (colonnes Topic | Check + exemples) a editer
    avant l'import."""
    if not _CHECKLIST_TEMPLATE.is_file():
        raise AppError("TEMPLATE_MISSING", "Modele de checklist introuvable", status_code=404)
    return FileResponse(
        _CHECKLIST_TEMPLATE,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="checklist_template.xlsx",
    )


@router.post("/rules/inspect", response_model=SheetInspectOut)
def inspect_checklist(file: UploadFile) -> SheetInspectOut:
    """Liste les onglets + grille d'apercu + ligne d'en-tete detectee d'un .xlsx
    (pour piloter le mapping des colonnes cote UI avant l'import)."""
    data = read_upload_limited(file, settings.max_upload_size_bytes)
    try:
        sheets = list_sheets(data)
    except Exception as exc:  # noqa: BLE001
        raise AppError("BAD_XLSX", f"Fichier Excel illisible : {exc}", status_code=400) from exc
    return SheetInspectOut(sheets=[SheetInfo(**s) for s in sheets])


def _name_key(name: str) -> str:
    return " ".join(name.split()).strip().lower()


def _compiled_summary(row: CompiledRuleVersion) -> CompiledRuleSummary:
    rule = validate_compiled_rule_json(row.compiled_json)
    return CompiledRuleSummary(
        id=rule.id,
        topic=rule.topic,
        severity=rule.severity,
        execution=rule.execution,
        active=row.active,
        source=rule.source,
        standard_id=None,
        standard_version_id=None,
        origin_ref=rule.origin_ref,
        semantic_instruction=rule.semantic_instruction,
        manual_instruction=rule.manual_instruction,
        compilation_error=rule.compilation_error,
        detail=describe_compiled_rule(rule),
    )


@router.get("/compiled-rules", response_model=list[CompiledRuleSummary])
def list_compiled_rules(
    standard_version_id: list[uuid.UUID] = Query(default=[]),
    db: Session = Depends(get_db),
) -> list[CompiledRuleSummary]:
    summaries: dict[str, CompiledRuleSummary] = {}
    versions: list[StandardVersion] = []
    if standard_version_id:
        versions = list(
            db.scalars(
                select(StandardVersion)
                .where(StandardVersion.id.in_(standard_version_id))
                .order_by(StandardVersion.created_at)
            )
        )
    for version in versions:
        try:
            disabled_codes = set(json.loads(version.disabled_rule_codes or "[]"))
        except (TypeError, ValueError):
            disabled_codes = set()
        try:
            catalog = json.loads(version.catalog_json or "[]")
        except (TypeError, ValueError):
            catalog = []
        for source in catalog if isinstance(catalog, list) else []:
            code = str(source.get("code") or "")
            rule = compile_standard_rule(
                source,
                f"{version.standard.code}:{version.label}:{source.get('code', '')}",
            )
            if rule is not None:
                summaries[rule.id] = CompiledRuleSummary(
                    id=rule.id,
                    topic=rule.topic,
                    severity=rule.severity,
                    execution=rule.execution,
                    active=code not in disabled_codes,
                    source=rule.source,
                    standard_id=version.standard_id,
                    standard_version_id=version.id,
                    origin_ref=rule.origin_ref,
                    semantic_instruction=rule.semantic_instruction,
                    detail=describe_compiled_rule(rule),
                )
    rows = list(
        db.scalars(
            select(CompiledRuleVersion).order_by(CompiledRuleVersion.created_at.desc())
        )
    )
    for row in rows:
        summary = _compiled_summary(row)
        summaries[summary.id] = summary
    return list(summaries.values())


@router.patch("/compiled-rules/{rule_id}", response_model=CompiledRuleSummary)
def patch_compiled_rule(
    rule_id: str,
    body: CompiledRulePatchIn,
    db: Session = Depends(get_db),
) -> CompiledRuleSummary:
    row = db.scalar(
        select(CompiledRuleVersion)
        .where(
            CompiledRuleVersion.code == rule_id,
            CompiledRuleVersion.source == "user_checklist",
        )
        .order_by(desc(CompiledRuleVersion.created_at))
        .limit(1)
    )
    if row is None:
        raise AppError("COMPILED_RULE_NOT_FOUND", "Règle compilée introuvable", status_code=404)
    row.active = body.active
    db.commit()
    db.refresh(row)
    return _compiled_summary(row)


@router.post("/rules/import", response_model=RuleImportResult)
def import_checklist(
    request: Request,
    file: UploadFile,
    sheet: Optional[str] = Form(default=None),
    mapping: Optional[str] = Form(default=None),
    mode: str = Form(default="replace"),
    db: Session = Depends(get_db),
) -> RuleImportResult:
    """Compile chaque ligne via Mistral et conserve tous les résultats typés.

    Les règles déterministes valides sont actives immédiatement. Les règles
    manuelles ou non supportées restent persistées et visibles, sans être exécutées.
    """
    if mode not in {"replace", "add"}:
        raise AppError("BAD_MODE", f"Mode d'import inconnu : {mode}.", status_code=400)

    data = read_upload_limited(file, settings.max_upload_size_bytes)
    parsed_mapping: Optional[dict] = None
    if mapping:
        try:
            parsed_mapping = json.loads(mapping)
        except json.JSONDecodeError as exc:
            raise AppError("BAD_MAPPING", "Mapping de colonnes invalide (JSON).", status_code=400) from exc

    try:
        parsed = parse_checklist(data, sheet=sheet, mapping=parsed_mapping)
    except Exception as exc:  # noqa: BLE001
        raise AppError("BAD_XLSX", f"Checklist illisible : {exc}", status_code=400) from exc

    replaced_count = 0
    if mode == "replace":
        existing = list(
            db.scalars(
                select(CompiledRuleVersion).where(
                    CompiledRuleVersion.source == "user_checklist"
                )
            )
        )
        replaced_count = len(existing)
        db.execute(
            delete(CompiledRuleVersion).where(
                CompiledRuleVersion.source == "user_checklist"
            )
        )
        db.execute(delete(Rule).where(Rule.kind.in_(_CHECKLIST_KINDS)))

    existing_keys: set[str] = set()
    if mode == "add":
        existing_keys = {
            code for (code,) in db.execute(
                select(CompiledRuleVersion.code).where(
                    CompiledRuleVersion.source == "user_checklist"
                )
            )
        }

    imported = 0
    skipped_manual = 0
    by_kind: dict[str, int] = {}
    seen: set[str] = set(existing_keys)
    compiled_rows: list[CompiledRuleVersion] = []
    for pr in parsed:
        compiled = compile_checklist_rule(
            db,
            pr,
            file.filename or "checklist.xlsx",
            client_bundle=request.app.state.client_configuration.bundle,
        )
        if compiled.id in seen:
            continue
        seen.add(compiled.id)
        row = persist_compiled_rule(db, compiled)
        compiled_rows.append(row)
        imported += 1
        by_kind[compiled.execution] = by_kind.get(compiled.execution, 0) + 1

    db.commit()
    return RuleImportResult(
        mode=mode,
        imported=imported,
        replaced_count=replaced_count,
        by_kind=by_kind,
        skipped_manual=skipped_manual,
        rules=[_compiled_summary(row) for row in compiled_rows],
    )


@router.post("/rules/validate-all", response_model=dict)
def validate_all(db: Session = Depends(get_db)) -> dict:
    """Active toutes les règles checklist compilables encore désactivées."""
    rows = list(
        db.scalars(
            select(CompiledRuleVersion).where(
                CompiledRuleVersion.source == "user_checklist",
                CompiledRuleVersion.active.is_(False),
            )
        )
    )
    activated = 0
    for row in rows:
        rule = validate_compiled_rule_json(row.compiled_json)
        if rule.execution in {"deterministic", "semantic", "manual"}:
            row.active = True
            activated += 1
    db.commit()
    return {"activated": activated}


@router.post("/rules/suggest/from-files", response_model=RuleSuggestOut)
def suggest_rules_from_files(
    files: list[UploadFile] = File(...),
    standard_version_id: Optional[uuid.UUID] = Form(default=None),
    db: Session = Depends(get_db),
) -> RuleSuggestOut:
    """Suggere des regles a partir de documents CONFORMES uploades directement
    (PDF / .doc / .docx) — pour baser les suggestions sur du bon contenu, sans
    dependre des documents en cours de revue. `standard_version_id` scope les
    regles proposees a une norme (optionnel)."""
    import fitz  # PyMuPDF

    if len(files) > _SUGGEST_MAX_DOCS:
        raise AppError(
            "RULE_SUGGEST_TOO_MANY_DOCUMENTS",
            f"Sélectionnez au plus {_SUGGEST_MAX_DOCS} fichiers; aucun fichier n'a été ignoré.",
            status_code=413,
        )

    samples: list[str] = []
    analyzed = 0
    for f in files[:_SUGGEST_MAX_DOCS]:
        data = read_upload_limited(f, settings.max_upload_size_bytes)
        try:
            pdf_bytes, name, _engine = ingest.to_pdf_bytes(f.filename or "upload", data)
        except AppError as exc:
            raise AppError(
                "RULE_SUGGEST_INPUT_INCOMPLETE",
                "Un fichier du périmètre n'a pas pu être converti; aucune suggestion n'a été produite.",
                status_code=422,
            ) from exc
        try:
            fdoc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = "\n".join(p.get_text() for p in fdoc)
            fdoc.close()
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                "RULE_SUGGEST_INPUT_INCOMPLETE",
                "Un fichier du périmètre n'a pas pu être analysé intégralement; aucune suggestion n'a été produite.",
                status_code=422,
            ) from exc
        text = (text or "").strip()
        if not text:
            raise AppError(
                "RULE_SUGGEST_INPUT_INCOMPLETE",
                "Un fichier du périmètre ne contient pas de texte analysable; aucune suggestion n'a été produite.",
                status_code=422,
            )
        snippet, was_truncated = _truncate_sample(text, _SUGGEST_PER_DOC_BUDGET)
        if was_truncated:
            truncated += 1
        samples.append(f"=== {name} ===\n{snippet}")
        analyzed += 1

    if not samples:
        raise AppError(
            "NO_TEXT_FOR_SUGGESTIONS",
            "Aucun texte exploitable dans les fichiers conformes fournis "
            "(PDF scanne sans couche texte, ou conversion Word indisponible).",
            status_code=400,
        )

    try:
        items = suggest_rules_from_corpus(db, samples, standard_context=None)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "RULE_SUGGEST_FAILED",
            f"Mistral a echoue : {type(exc).__name__}: {exc}",
            status_code=502,
        ) from exc

    return RuleSuggestOut(
        suggestions=[
            RuleSuggestionItem(**{**item, "standard_version_id": standard_version_id})
            for item in items
        ],
        documents_analyzed=analyzed,
        documents_truncated=truncated,
    )
