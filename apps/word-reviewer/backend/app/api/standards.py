"""Routes /api/v1/standards - referentiels + edition du catalogue de regles.

Le catalogue d'une `StandardVersion` est stocke en JSON (`catalog_json`). On
expose un CRUD complet sur ses regles (lister / ajouter / modifier / supprimer /
activer-desactiver) + une restauration d'usine. L'edition **en place du builtin
ATA100 est autorisee** (le seed est idempotent, les edits persistent) ; le bouton
reset restaure depuis `BUILTIN_STANDARDS`.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.rules_engine import validate_rule_pattern
from app.db.models import Rule, Standard, StandardVersion
from app.db.session import get_db
from app.schemas import (
    CatalogRuleIn,
    CatalogRuleOut,
    CatalogRulePatchIn,
    CatalogToggleIn,
    RuleOut,
    StandardOut,
    StandardVersionDetailOut,
    StandardVersionOut,
)


router = APIRouter(prefix="/standards", tags=["standards"])

_PATCHABLE = {
    "title", "description", "kind", "severity", "pattern",
    "replacement", "message", "example_invalid", "example_valid", "metadata",
}


def _version_out(sv: StandardVersion) -> StandardVersionOut:
    try:
        count = len(json.loads(sv.catalog_json or "[]"))
    except (ValueError, TypeError):
        count = 0
    return StandardVersionOut(id=sv.id, label=sv.label, builtin=sv.builtin, rule_count=count)


def _load_catalog(version: StandardVersion) -> list[dict]:
    try:
        loaded = json.loads(version.catalog_json or "[]")
    except (ValueError, TypeError):
        return []
    return [r for r in loaded if isinstance(r, dict)]


def _load_disabled(version: StandardVersion) -> list[str]:
    try:
        codes = json.loads(version.disabled_rule_codes or "[]")
    except (ValueError, TypeError):
        return []
    return [str(c) for c in codes if str(c).strip()] if isinstance(codes, list) else []


def _save_catalog(version: StandardVersion, catalog: list[dict]) -> None:
    version.catalog_json = json.dumps(catalog, ensure_ascii=False)


def _get_version(db: Session, standard_id: uuid.UUID, version_id: uuid.UUID) -> StandardVersion:
    version = db.get(StandardVersion, version_id)
    if version is None or version.standard_id != standard_id:
        raise AppError("VERSION_NOT_FOUND", "Version de standard introuvable.", 404)
    return version


def _rule_source(entry: dict) -> str:
    md = entry.get("metadata") or {}
    if md.get("source"):
        return str(md["source"])
    return "CMM" if str(entry.get("code", "")).upper().startswith("CMM") else "ATA 100"


def _detail(db: Session, version: StandardVersion) -> StandardVersionDetailOut:
    catalog: list[CatalogRuleOut] = []
    for r in _load_catalog(version):
        out = CatalogRuleOut.model_validate(r)
        out.source = _rule_source(r)
        catalog.append(out)
    custom = list(
        db.scalars(select(Rule).where(Rule.standard_version_id == version.id).order_by(Rule.created_at))
    )
    return StandardVersionDetailOut(
        id=version.id,
        label=version.label,
        builtin=version.builtin,
        catalog=catalog,
        disabled_rule_codes=_load_disabled(version),
        custom_rules=[RuleOut.model_validate(r) for r in custom],
    )


@router.get("", response_model=list[StandardOut])
def list_standards(db: Session = Depends(get_db)) -> list[StandardOut]:
    out: list[StandardOut] = []
    for std in db.scalars(select(Standard).order_by(Standard.code)):
        versions = [_version_out(v) for v in std.versions]
        out.append(
            StandardOut(
                id=std.id,
                code=std.code,
                label=std.label,
                description=std.description,
                builtin=std.builtin,
                versions=versions,
            )
        )
    return out


@router.get("/{standard_id}/versions/{version_id}", response_model=StandardVersionDetailOut)
def get_version_detail(
    standard_id: uuid.UUID, version_id: uuid.UUID, db: Session = Depends(get_db)
) -> StandardVersionDetailOut:
    return _detail(db, _get_version(db, standard_id, version_id))


@router.post("/{standard_id}/versions/{version_id}/rules", response_model=StandardVersionDetailOut)
def add_catalog_rule(
    standard_id: uuid.UUID,
    version_id: uuid.UUID,
    body: CatalogRuleIn,
    db: Session = Depends(get_db),
) -> StandardVersionDetailOut:
    version = _get_version(db, standard_id, version_id)
    code = body.code.strip()
    if not code:
        raise AppError("CODE_REQUIRED", "Le code de la regle est obligatoire.", 400)
    catalog = _load_catalog(version)
    if any(r.get("code") == code for r in catalog):
        raise AppError("CODE_TAKEN", f"Le code '{code}' existe deja dans ce catalogue.", 409)
    validate_rule_pattern(body.pattern, body.kind)
    entry = body.model_dump()
    entry["code"] = code
    md = dict(entry.get("metadata") or {})
    md.setdefault("source", "Ajoutee")
    entry["metadata"] = md
    catalog.append(entry)
    _save_catalog(version, catalog)
    db.commit()
    db.refresh(version)
    return _detail(db, version)


@router.patch(
    "/{standard_id}/versions/{version_id}/rules/{code}", response_model=StandardVersionDetailOut
)
def patch_catalog_rule(
    standard_id: uuid.UUID,
    version_id: uuid.UUID,
    code: str,
    body: CatalogRulePatchIn,
    db: Session = Depends(get_db),
) -> StandardVersionDetailOut:
    version = _get_version(db, standard_id, version_id)
    catalog = _load_catalog(version)
    idx = next((i for i, r in enumerate(catalog) if r.get("code") == code), -1)
    if idx < 0:
        raise AppError("CODE_UNKNOWN", f"Regle inconnue : {code}.", 404)
    patch = body.model_dump(exclude_unset=True)
    if "pattern" in patch and patch["pattern"]:
        kind = patch.get("kind") or catalog[idx].get("kind") or ""
        validate_rule_pattern(patch["pattern"], kind)
    for key, value in patch.items():
        if key in _PATCHABLE:
            catalog[idx][key] = value
    _save_catalog(version, catalog)
    db.commit()
    db.refresh(version)
    return _detail(db, version)


@router.delete(
    "/{standard_id}/versions/{version_id}/rules/{code}", response_model=StandardVersionDetailOut
)
def delete_catalog_rule(
    standard_id: uuid.UUID, version_id: uuid.UUID, code: str, db: Session = Depends(get_db)
) -> StandardVersionDetailOut:
    version = _get_version(db, standard_id, version_id)
    catalog = _load_catalog(version)
    new_catalog = [r for r in catalog if r.get("code") != code]
    if len(new_catalog) == len(catalog):
        raise AppError("CODE_UNKNOWN", f"Regle inconnue : {code}.", 404)
    _save_catalog(version, new_catalog)
    db.commit()
    db.refresh(version)
    return _detail(db, version)


@router.post(
    "/{standard_id}/versions/{version_id}/rules/toggle", response_model=StandardVersionDetailOut
)
def toggle_catalog_rule(
    standard_id: uuid.UUID,
    version_id: uuid.UUID,
    body: CatalogToggleIn,
    db: Session = Depends(get_db),
) -> StandardVersionDetailOut:
    version = _get_version(db, standard_id, version_id)
    valid = {str(r.get("code")) for r in _load_catalog(version) if r.get("code")}
    if body.code not in valid:
        raise AppError("CODE_UNKNOWN", f"Regle inconnue : {body.code}.", 400)
    disabled = set(_load_disabled(version))
    if body.enabled:
        disabled.discard(body.code)
    else:
        disabled.add(body.code)
    version.disabled_rule_codes = json.dumps(sorted(disabled), ensure_ascii=False)
    db.commit()
    db.refresh(version)
    return _detail(db, version)


@router.post("/{standard_id}/versions/{version_id}/reset", response_model=StandardVersionDetailOut)
def reset_catalog(
    standard_id: uuid.UUID, version_id: uuid.UUID, db: Session = Depends(get_db)
) -> StandardVersionDetailOut:
    """Restaure le catalogue d'usine depuis BUILTIN_STANDARDS (+ reactive tout)."""
    from app.checks.standards import BUILTIN_STANDARDS

    version = _get_version(db, standard_id, version_id)
    std = db.get(Standard, standard_id)
    if std is None:
        raise AppError("NOT_FOUND", "Standard introuvable.", 404)
    factory: list[dict] | None = None
    for spec in BUILTIN_STANDARDS:
        if spec["code"] != std.code:
            continue
        for label, rules in spec["versions"].items():  # type: ignore[union-attr]
            if label == version.label:
                factory = [r.as_dict() for r in rules]
    if factory is None:
        raise AppError("NOT_RESETTABLE", "Aucun catalogue d'usine pour cette version.", 400)
    _save_catalog(version, factory)
    version.disabled_rule_codes = "[]"
    db.commit()
    db.refresh(version)
    return _detail(db, version)
