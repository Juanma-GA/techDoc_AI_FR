"""Persist and serve the last migration form input mapping."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import AppConfig, Document
from app.db.session import storage_directory

MAPPING_KEY = "migration_input_mapping"
INPUT_KINDS = ("document", "dmrl", "cir", "brex_rules", "dm_header")
_RESOURCE_FIELDS = {
    "dmrl": "dmrl_path",
    "cir": "cir_path",
    "brex_rules": "brex_rules_path",
    "dm_header": "dm_header_path",
}


def _default_mapping() -> dict:
    return {
        "issue": "4.2",
        "context_hint": "mixed",
        "brex_id": None,
        "files": {},
    }


def _normalize(value: object) -> dict:
    if not isinstance(value, dict):
        return _default_mapping()
    mapping = _default_mapping()
    issue = value.get("issue")
    if issue in {"4.1", "4.2", "5.0"}:
        mapping["issue"] = issue
    hint = value.get("context_hint")
    if hint in {"mixed", "descriptive", "procedural"}:
        mapping["context_hint"] = hint
    brex_id = value.get("brex_id")
    mapping["brex_id"] = brex_id if isinstance(brex_id, str) and brex_id else None

    raw_files = value.get("files")
    if isinstance(raw_files, dict):
        files: dict[str, dict[str, str]] = {}
        for kind in INPUT_KINDS:
            item = raw_files.get(kind)
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            filename = item.get("filename")
            if isinstance(path, str) and path and isinstance(filename, str) and filename:
                files[kind] = {"path": path, "filename": filename}
        mapping["files"] = files
    return mapping


def load(db: Session) -> dict:
    config = db.get(AppConfig, MAPPING_KEY)
    if config is None or not config.value:
        return _default_mapping()
    try:
        return _normalize(json.loads(config.value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return _default_mapping()


def _save(db: Session, mapping: dict) -> None:
    config = db.get(AppConfig, MAPPING_KEY)
    if config is None:
        config = AppConfig(key=MAPPING_KEY, value="")
        db.add(config)
    config.value = json.dumps(mapping, ensure_ascii=False)


def save_document(
    db: Session,
    document: Document,
    *,
    filename: str | None = None,
    resource_filename: tuple[str, str] | None = None,
) -> None:
    """Update the latest input mapping without changing the current document."""
    mapping = load(db)
    mapping["issue"] = document.s1000d_issue
    mapping["context_hint"] = document.context_hint
    mapping["brex_id"] = document.brex_id
    files = mapping["files"]
    files["document"] = {
        "path": document.storage_path,
        "filename": filename or document.filename,
    }
    for kind, field in _RESOURCE_FIELDS.items():
        path = getattr(document, field)
        if not path:
            continue
        previous = files.get(kind) or {}
        saved_name = previous.get("filename") or Path(path).name
        if resource_filename and resource_filename[0] == kind:
            saved_name = resource_filename[1]
        files[kind] = {"path": path, "filename": saved_name}
    _save(db, mapping)


def public(db: Session) -> dict:
    mapping = load(db)
    files = {}
    for kind, item in mapping["files"].items():
        if _safe_path(item["path"], db) is not None:
            files[kind] = {"filename": item["filename"]}
    return {
        "issue": mapping["issue"],
        "context_hint": mapping["context_hint"],
        "brex_id": mapping["brex_id"],
        "files": files,
    }


def saved_file(db: Session, kind: str) -> tuple[Path, str] | None:
    if kind not in INPUT_KINDS:
        return None
    item = load(db)["files"].get(kind)
    if not item:
        return None
    path = _safe_path(item["path"], db)
    return (path, item["filename"]) if path is not None else None


def remove_resource(db: Session, document: Document, kind: str) -> None:
    mapping = load(db)
    if mapping["files"].get("document", {}).get("path") == document.storage_path:
        mapping["files"].pop(kind, None)
        _save(db, mapping)


def _safe_path(raw_path: str, db: Session) -> Path | None:
    path = Path(raw_path)
    root = storage_directory(db).resolve()
    try:
        path = path.resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return None
    return path if path.is_file() else None
