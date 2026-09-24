"""Synchronize file-backed standard catalogs at startup."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.checks.standards import CUSTOM_STANDARD_SPECS, serialize_builtin_version
from app.core.logging import get_logger
from app.db.models import Standard, StandardVersion


_logger = get_logger(__name__)


def sync_custom_standards(
    db: Session,
    client_standard_specs: Mapping[str, Mapping[str, object]] | None = None,
) -> int:
    """Create and refresh all file-backed client standard catalogs.

    The published built-in catalogs remain database-owned after their Alembic
    migrations. Client catalogs are sourced from the discovered ``*_custom``
    modules so they can be edited and tested after a backend restart without a
    new migration for every rule change.
    """
    now = datetime.now(timezone.utc)
    changed = 0
    standard_specs = (
        list(client_standard_specs.values())
        if client_standard_specs is not None
        else CUSTOM_STANDARD_SPECS
    )
    for spec in standard_specs:
        code = str(spec["code"])
        label = str(spec["label"])
        description = str(spec["description"])
        standard = db.scalar(select(Standard).where(Standard.code == code))
        if standard is None and code == "THALES-CUSTOM":
            standard = db.scalar(
                select(Standard).where(Standard.code == "ATEXIS-CUSTOM")
            )
            if standard is not None:
                standard.code = code
        if standard is None:
            standard = Standard(
                code=code,
                label=label,
                description=description,
                builtin=True,
            )
            db.add(standard)
            db.flush()
        else:
            standard.label = label
            standard.description = description

        versions = spec["versions"]
        for version_label in versions:
            payload = json.dumps(
                serialize_builtin_version(spec, version_label),
                ensure_ascii=False,
            )
            version = db.scalar(
                select(StandardVersion).where(
                    StandardVersion.standard_id == standard.id,
                    StandardVersion.label == version_label,
                )
            )
            if version is None:
                db.add(
                    StandardVersion(
                        standard_id=standard.id,
                        label=version_label,
                        builtin=True,
                        catalog_json=payload,
                    )
                )
                changed += 1
            elif version.catalog_json != payload:
                version.catalog_json = payload
                version.updated_at = now
                changed += 1

    db.commit()
    if changed:
        _logger.info("custom_standards_synced", changed_versions=changed)
    return changed


def sync_user_standard(
    db: Session,
    client_standard_specs: Mapping[str, Mapping[str, object]] | None = None,
) -> int:
    """Backward-compatible alias for the generic client catalog sync."""
    return sync_custom_standards(db, client_standard_specs)
