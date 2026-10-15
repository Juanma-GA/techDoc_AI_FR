from collections.abc import Iterable
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.checks.client_registry import LoadedClientConfiguration, active_standard_versions
from app.core.demo_mode import get_demo_enabled
from app.db.models import Standard


def get_request_client_configuration(
    request: Request,
    db: Session,
) -> LoadedClientConfiguration:
    if get_demo_enabled(db):
        return request.app.state.demo_client_configuration
    return request.app.state.client_configuration


def visible_client_standards(
    request: Request,
    db: Session,
    standards: Iterable[Standard],
) -> list[Standard]:
    configuration = get_request_client_configuration(request, db)
    client_catalog_codes = {
        catalog.code
        for candidate in (
            request.app.state.client_configuration,
            request.app.state.demo_client_configuration,
        )
        for catalog in candidate.bundle.catalogs
    }
    active_catalog_codes = {
        catalog.code for catalog in configuration.bundle.catalogs
    }
    return [
        standard
        for standard in standards
        if standard.code not in client_catalog_codes
        or standard.code in active_catalog_codes
    ]


def analysis_standard_version_ids(
    request: Request,
    db: Session,
    stored_ids: list[str],
    legacy_id: UUID | None,
) -> list[str]:
    configuration = get_request_client_configuration(request, db)
    if get_demo_enabled(db):
        return [
            str(version.id)
            for version in active_standard_versions(db, configuration)
        ]

    demo_ids = {
        str(version.id)
        for version in active_standard_versions(
            db,
            request.app.state.demo_client_configuration,
        )
    }
    selected = [version_id for version_id in stored_ids if version_id not in demo_ids]
    if not selected and legacy_id is not None and str(legacy_id) not in demo_ids:
        selected = [str(legacy_id)]
    if selected:
        return selected
    return [
        str(version.id)
        for version in active_standard_versions(db, configuration)
    ]
