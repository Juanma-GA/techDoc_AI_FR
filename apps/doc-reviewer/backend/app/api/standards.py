"""Standards CRUD — list / create / patch / delete + versions sub-resource.

Built-in entries (`builtin=True`) are read-only: any write attempt yields
a 409 `STANDARD_BUILTIN_PROTECTED`. Custom standards (and their custom
versions) are fully editable; they can be cloned from a built-in via
the `POST /standards/{id}/versions` endpoint with a copied `catalog`.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.checks.mode_registry import (
    get_request_client_configuration,
    visible_client_standards,
)
from app.core.errors import AppError
from app.core.rules_engine import validate_rule_pattern
from app.db.models import Rule, Standard, StandardVersion
from app.db.session import get_db
from app.schemas import (
    CatalogRuleOut,
    CatalogRulePatchIn,
    RuleOut,
    StandardIn,
    StandardOut,
    StandardPatchIn,
    StandardVersionDetailOut,
    StandardVersionIn,
    StandardVersionOut,
)


class RuleToggleIn(BaseModel):
    code: str
    enabled: bool


router = APIRouter(tags=["standards"])


@router.get("/standards", response_model=list[StandardOut])
def list_standards(
    request: Request,
    db: Session = Depends(get_db),
) -> list[Standard]:
    stmt = (
        select(Standard)
        .options(selectinload(Standard.versions))
        .order_by(Standard.builtin.desc(), Standard.code)
    )
    return visible_client_standards(request, db, db.scalars(stmt))


@router.post("/standards", response_model=StandardOut, status_code=201)
def create_standard(body: StandardIn, db: Session = Depends(get_db)) -> Standard:
    existing = db.scalar(select(Standard).where(Standard.code == body.code))
    if existing is not None:
        raise AppError(
            "STANDARD_CODE_TAKEN",
            f"Le code '{body.code}' est déjà utilisé.",
            status_code=409,
        )
    std = Standard(
        code=body.code.strip(),
        label=body.label.strip(),
        description=body.description,
        builtin=False,
    )
    db.add(std)
    db.commit()
    db.refresh(std)
    return std


@router.patch("/standards/{standard_id}", response_model=StandardOut)
def patch_standard(
    standard_id: uuid.UUID,
    body: StandardPatchIn,
    db: Session = Depends(get_db),
) -> Standard:
    std = db.get(Standard, standard_id)
    if std is None:
        raise AppError("STANDARD_NOT_FOUND", "Norme introuvable", status_code=404)
    if std.builtin:
        raise AppError(
            "STANDARD_BUILTIN_PROTECTED",
            "Norme built-in en lecture seule.",
            status_code=409,
        )
    if body.label is not None:
        std.label = body.label
    if body.description is not None:
        std.description = body.description
    std.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(std)
    return std


@router.delete("/standards/{standard_id}", status_code=204)
def delete_standard(standard_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    std = db.get(Standard, standard_id)
    if std is None:
        raise AppError("STANDARD_NOT_FOUND", "Norme introuvable", status_code=404)
    if std.builtin:
        raise AppError(
            "STANDARD_BUILTIN_PROTECTED",
            "Norme built-in non supprimable.",
            status_code=409,
        )
    db.delete(std)
    db.commit()


@router.post(
    "/standards/{standard_id}/versions",
    response_model=StandardVersionOut,
    status_code=201,
)
def create_version(
    standard_id: uuid.UUID,
    body: StandardVersionIn,
    db: Session = Depends(get_db),
) -> StandardVersion:
    std = db.get(Standard, standard_id)
    if std is None:
        raise AppError("STANDARD_NOT_FOUND", "Norme introuvable", status_code=404)
    if std.builtin:
        raise AppError(
            "STANDARD_BUILTIN_PROTECTED",
            "Ajout de version interdit sur une norme built-in (clonez-la d'abord).",
            status_code=409,
        )
    duplicate = db.scalar(
        select(StandardVersion).where(
            StandardVersion.standard_id == standard_id,
            StandardVersion.label == body.label,
        )
    )
    if duplicate is not None:
        raise AppError(
            "STANDARD_VERSION_TAKEN",
            f"La version '{body.label}' existe déjà pour cette norme.",
            status_code=409,
        )
    version = StandardVersion(
        standard_id=standard_id,
        label=body.label.strip(),
        builtin=False,
        catalog_json=json.dumps(body.catalog, ensure_ascii=False),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.delete("/standards/{standard_id}/versions/{version_id}", status_code=204)
def delete_version(
    standard_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    version = db.get(StandardVersion, version_id)
    if version is None or version.standard_id != standard_id:
        raise AppError("STANDARD_VERSION_NOT_FOUND", "Version introuvable", status_code=404)
    if version.builtin:
        raise AppError(
            "STANDARD_BUILTIN_PROTECTED",
            "Version built-in non supprimable.",
            status_code=409,
        )
    db.delete(version)
    db.commit()


@router.get(
    "/standards/{standard_id}/versions/{version_id}",
    response_model=StandardVersionDetailOut,
)
def get_version_detail(
    standard_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Return the version + its built-in catalog + custom rules attached +
    the list of disabled rule codes (toggle state per built-in rule)."""
    version = db.get(StandardVersion, version_id)
    if version is None or version.standard_id != standard_id:
        raise AppError("STANDARD_VERSION_NOT_FOUND", "Version introuvable", status_code=404)
    try:
        catalog_raw = json.loads(version.catalog_json or "[]")
    except json.JSONDecodeError:
        catalog_raw = []
    catalog = [CatalogRuleOut.model_validate(item) for item in catalog_raw if isinstance(item, dict)]
    try:
        disabled_codes = json.loads(version.disabled_rule_codes or "[]")
    except json.JSONDecodeError:
        disabled_codes = []
    if not isinstance(disabled_codes, list):
        disabled_codes = []
    custom = list(
        db.scalars(select(Rule).where(Rule.standard_version_id == version_id).order_by(Rule.created_at))
    )
    base = StandardVersionOut.model_validate(version).model_dump(mode="json")
    base["catalog"] = [c.model_dump(mode="json") for c in catalog]
    base["custom_rules"] = [RuleOut.model_validate(r).model_dump(mode="json") for r in custom]
    base["disabled_rule_codes"] = [str(c) for c in disabled_codes if str(c).strip()]
    return base


_PATCHABLE_FIELDS = {
    "title", "description", "description_en", "severity", "kind",
    "pattern", "replacement", "message", "message_en",
    "example_invalid", "example_valid",
}


def _load_catalog_list(version: StandardVersion) -> list[dict]:
    try:
        loaded = json.loads(version.catalog_json or "[]")
    except json.JSONDecodeError:
        return []
    return [r for r in loaded if isinstance(r, dict)]


@router.patch(
    "/standards/{standard_id}/versions/{version_id}/rules/{code}",
    response_model=StandardVersionDetailOut,
)
def patch_catalog_rule(
    standard_id: uuid.UUID,
    version_id: uuid.UUID,
    code: str,
    body: CatalogRulePatchIn,
    db: Session = Depends(get_db),
) -> dict:
    """Expert edit on a built-in or custom catalog rule. Mutates the
    `catalog_json` payload in place. Works on built-in versions too —
    the user explicitly chose to override the factory rule; the
    `POST .../reset` endpoint restores the factory copy from Python source.
    """
    version = db.get(StandardVersion, version_id)
    if version is None or version.standard_id != standard_id:
        raise AppError("STANDARD_VERSION_NOT_FOUND", "Version introuvable", status_code=404)

    catalog = _load_catalog_list(version)
    idx = next((i for i, r in enumerate(catalog) if r.get("code") == code), -1)
    if idx < 0:
        raise AppError(
            "CATALOG_CODE_UNKNOWN",
            f"Code de règle inconnu pour cette version : {code}",
            status_code=404,
        )

    patch = body.model_dump(exclude_unset=True)
    # Validate regex patterns up-front so a bad edit can't poison analyse.
    if "pattern" in patch and patch["pattern"]:
        kind = patch.get("kind") or catalog[idx].get("kind") or ""
        if kind in {"regex_replace", "regex_flag", "step_pattern"}:
            validate_rule_pattern(patch["pattern"])

    for key, value in patch.items():
        if key in _PATCHABLE_FIELDS:
            catalog[idx][key] = value

    version.catalog_json = json.dumps(catalog, ensure_ascii=False)
    db.commit()
    db.refresh(version)
    return get_version_detail(standard_id, version_id, db)


@router.post(
    "/standards/{standard_id}/versions/{version_id}/rules/{code}/reset",
    response_model=StandardVersionDetailOut,
)
def reset_catalog_rule(
    standard_id: uuid.UUID,
    version_id: uuid.UUID,
    code: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Restore a built-in catalog rule from the Python source of truth
    (`app.checks.standards.*`). No-op for custom versions or codes not
    present in the factory catalog."""
    from app.checks.standards import BUILTIN_STANDARDS, serialize_builtin_version

    version = db.get(StandardVersion, version_id)
    if version is None or version.standard_id != standard_id:
        raise AppError("STANDARD_VERSION_NOT_FOUND", "Version introuvable", status_code=404)

    std = db.get(Standard, standard_id)
    if std is None or not version.builtin:
        raise AppError(
            "CATALOG_NOT_RESETTABLE",
            "Seules les règles built-in peuvent être restaurées.",
            status_code=400,
        )

    factory_rule = None
    factory_specs = [
        *BUILTIN_STANDARDS,
        *get_request_client_configuration(request, db).bundle.standard_specs.values(),
    ]
    for spec in factory_specs:
        if spec["code"] != std.code:
            continue
        for label in spec["versions"]:
            if label != version.label:
                continue
            factory_rule = next(
                (
                    item
                    for item in serialize_builtin_version(spec, label)
                    if item.get("code") == code
                ),
                None,
            )
    if factory_rule is None:
        raise AppError(
            "CATALOG_CODE_UNKNOWN",
            f"Aucune version factory de {code} disponible.",
            status_code=404,
        )

    catalog = _load_catalog_list(version)
    idx = next((i for i, r in enumerate(catalog) if r.get("code") == code), -1)
    if idx < 0:
        catalog.append(factory_rule)
    else:
        catalog[idx] = factory_rule
    version.catalog_json = json.dumps(catalog, ensure_ascii=False)
    db.commit()
    db.refresh(version)
    return get_version_detail(standard_id, version_id, db)


@router.post(
    "/standards/{standard_id}/versions/{version_id}/rules/toggle",
    response_model=StandardVersionDetailOut,
)
def toggle_catalog_rule(
    standard_id: uuid.UUID,
    version_id: uuid.UUID,
    body: RuleToggleIn,
    db: Session = Depends(get_db),
) -> dict:
    """Enable / disable a built-in catalog rule for the given standard
    version. Works on built-in AND custom versions (idempotent toggle).
    Returns the refreshed version detail."""
    version = db.get(StandardVersion, version_id)
    if version is None or version.standard_id != standard_id:
        raise AppError("STANDARD_VERSION_NOT_FOUND", "Version introuvable", status_code=404)
    try:
        catalog_raw = json.loads(version.catalog_json or "[]")
    except json.JSONDecodeError:
        catalog_raw = []
    valid_codes = {
        str(r.get("code"))
        for r in catalog_raw if isinstance(r, dict) and r.get("code")
    }
    if body.code not in valid_codes:
        raise AppError(
            "CATALOG_CODE_UNKNOWN",
            f"Code de règle inconnu pour cette version : {body.code}",
            status_code=400,
        )
    try:
        disabled = set(json.loads(version.disabled_rule_codes or "[]"))
    except json.JSONDecodeError:
        disabled = set()
    if body.enabled:
        disabled.discard(body.code)
    else:
        disabled.add(body.code)
    version.disabled_rule_codes = json.dumps(sorted(disabled), ensure_ascii=False)
    db.commit()
    db.refresh(version)
    return get_version_detail(standard_id, version_id, db)
