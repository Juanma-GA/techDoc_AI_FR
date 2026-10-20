"""Content-checked files; SQLite snapshots contain UUID references, not payloads."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import structlog
from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.db.models import FileAsset
from app.services.image_layout import _safe_filename_component
from app.services.saved_files import StoredFile
from app.workspace_schemas import StateModel

log = structlog.get_logger(__name__)


def _path(asset: FileAsset) -> Path:
    owner_id, asset_id = str(UUID(asset.owner_id)), str(UUID(asset.id))
    safe_name = _safe_filename_component(asset.name)[-80:]
    return Path(settings.storage_dir) / owner_id / f"{asset_id}_{safe_name}"


def _write_file(asset: FileAsset, contents: bytes) -> None:
    path = _path(asset)
    temporary = path.with_name(f".{asset.id}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(contents)
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        log.error("workspace_file_write_failed", asset_id=asset.id)
        raise AppError("STORAGE_WRITE_FAILED", "Unable to save the local file.", 500) from error


def _store(db: Session, owner_id: str, stored: StoredFile, created: list[Path]) -> str:
    asset = db.scalar(select(FileAsset).where(
        FileAsset.owner_id == owner_id, FileAsset.sha256 == stored.sha256, FileAsset.name == stored.name,
    ))
    if asset is None:
        asset = FileAsset(
            id=str(uuid4()), owner_id=owner_id, name=stored.name, sha256=stored.sha256,
            content_type=stored.data_url[5:stored.data_url.index(";base64,")],
            size_bytes=len(stored.contents()),
        )
        db.add(asset)
        db.flush()
        created.append(_path(asset))
        _write_file(asset, stored.contents())
    elif not _path(asset).is_file():
        log.warning("workspace_file_repaired", asset_id=asset.id)
        _write_file(asset, stored.contents())
    return asset.id


@contextmanager
def persist_state(
    db: Session, owner_id: str, state: StateModel,
) -> Iterator[tuple[str, set[str]]]:
    references: set[str] = set()
    created: list[Path] = []
    committed = False

    def replace(value: JsonValue) -> JsonValue:
        if isinstance(value, dict):
            if "data_url" in value:
                asset_id = _store(db, owner_id, StoredFile.model_validate(value), created)
                references.add(asset_id)
                return {"asset_id": asset_id}
            return {key: replace(child) for key, child in value.items()}
        if isinstance(value, list):
            return [replace(child) for child in value]
        return value

    try:
        yield json.dumps(replace(state.model_dump(mode="json", by_alias=True))), references
        db.commit()
        committed = True
    finally:
        if not committed:
            db.rollback()
            for path in created:
                try:
                    path.unlink(missing_ok=True)
                except OSError as error:
                    log.error("workspace_file_rollback_failed", owner_id=owner_id)
                    raise AppError(
                        "STORAGE_CLEANUP_FAILED", "Unable to clean up an interrupted local save.", 500,
                    ) from error


def restore_state(db: Session, owner_id: str, encoded: str) -> JsonValue:
    def replace(value: JsonValue) -> JsonValue:
        if isinstance(value, dict):
            if set(value) == {"asset_id"} and isinstance(value["asset_id"], str):
                asset = db.get(FileAsset, value["asset_id"])
                if asset is None or asset.owner_id != owner_id:
                    raise AppError("SAVED_FILE_MISSING", "The saved file reference is missing.", 500)
                try:
                    path = _path(asset)
                    if path.stat().st_size != asset.size_bytes:
                        raise AppError("SAVED_FILE_CORRUPT", "The saved file size has changed.", 500)
                    contents = path.read_bytes()
                except OSError as error:
                    log.error("workspace_file_read_failed", asset_id=asset.id)
                    raise AppError(
                        "SAVED_FILE_MISSING", "Unable to read the saved local file.", 500,
                    ) from error
                if sha256(contents).hexdigest() != asset.sha256:
                    log.error("workspace_file_checksum_failed", asset_id=asset.id)
                    raise AppError("SAVED_FILE_CORRUPT", "The saved file checksum has changed.", 500)
                encoded = base64.b64encode(contents).decode("ascii")
                return {
                    "name": asset.name, "sha256": asset.sha256,
                    "data_url": f"data:{asset.content_type};base64,{encoded}",
                }
            return {key: replace(child) for key, child in value.items()}
        if isinstance(value, list):
            return [replace(child) for child in value]
        return value

    return replace(json.loads(encoded))


def purge_assets(db: Session, owner_id: str, keep: set[str] | None = None) -> None:
    query = select(FileAsset).where(FileAsset.owner_id == owner_id)
    if keep:
        query = query.where(FileAsset.id.not_in(keep))
    assets = db.scalars(query).all()
    for asset in assets:
        try:
            _path(asset).unlink(missing_ok=True)
        except OSError as error:
            log.error("workspace_file_delete_failed", asset_id=asset.id)
            raise AppError("STORAGE_DELETE_FAILED", "Unable to delete the saved local file.", 500) from error
    for asset in assets:
        db.delete(asset)
    if assets:
        db.commit()
