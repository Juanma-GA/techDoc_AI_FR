"""Read-only CATPart folder comparison using exact hashes and partial geometry."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.core.catpart_geometry import (
    GeometryIssue,
    GeometrySignature,
    extract_geometry_signature,
    geometry_similarity,
    resolve_cadmpeg,
)
from app.core.errors import AppError

MAX_CATPART_FILES_PER_FOLDER = 100
_MIN_CANDIDATE_SIMILARITY = 25.0
_MAX_CANDIDATES_PER_FILE = 3


@dataclass(frozen=True)
class CatPartFile:
    absolute_path: Path
    relative_path: str
    sha256: str


def compare_folders(old_root: Path, new_root: Path) -> dict[str, object]:
    old_folder = _validate_folder(old_root, "old")
    new_folder = _validate_folder(new_root, "new")
    if old_folder == new_folder:
        raise AppError("CATPART_SAME_FOLDER", "Selectionnez deux dossiers differents.", status_code=400)

    old_files = _scan_folder(old_folder, "old")
    new_files = _scan_folder(new_folder, "new")
    old_by_hash = _group_by_hash(old_files)
    new_by_hash = _group_by_hash(new_files)
    shared_hashes = old_by_hash.keys() & new_by_hash.keys()
    exact_matches = [
        {
            "sha256": digest,
            "old_files": [item.relative_path for item in old_by_hash[digest]],
            "new_files": [item.relative_path for item in new_by_hash[digest]],
            "old_count": len(old_by_hash[digest]),
            "new_count": len(new_by_hash[digest]),
        }
        for digest in sorted(shared_hashes)
    ]
    unmatched_old = [item for item in old_files if item.sha256 not in shared_hashes]
    unmatched_new = [item for item in new_files if item.sha256 not in shared_hashes]
    issues: list[dict[str, str | None]] = []

    needs_geometry = bool(unmatched_old and unmatched_new)
    executable, reader_issue = resolve_cadmpeg() if needs_geometry else (None, None)
    signatures: dict[Path, GeometrySignature] = {}
    if needs_geometry and executable is None and reader_issue is not None:
        issues.append(_issue_dict(None, reader_issue))
    elif executable is not None:
        with tempfile.TemporaryDirectory(prefix="catpart-diff-") as temporary:
            output_dir = Path(temporary)
            pending = [*unmatched_old, *unmatched_new]
            for index, item in enumerate(pending):
                signature, issue = extract_geometry_signature(
                    item.absolute_path,
                    executable,
                    output_dir,
                    f"part-{index:03d}",
                )
                if signature is not None:
                    signatures[item.absolute_path] = signature
                if issue is not None:
                    issues.append(_issue_dict(item.relative_path, issue))

    candidates = _build_candidates(unmatched_old, unmatched_new, signatures)
    candidate_old = {item["old_file"] for item in candidates}
    candidate_new = {item["new_file"] for item in candidates}
    unmatched_old_paths = [
        item.relative_path for item in unmatched_old if item.relative_path not in candidate_old
    ]
    unmatched_new_paths = [
        item.relative_path for item in unmatched_new if item.relative_path not in candidate_new
    ]

    reader_available = executable is not None

    partial = bool(issues) or any(not signature.topology_complete for signature in signatures.values())
    status = (
        "empty"
        if not old_files or not new_files
        else ("partial" if partial or not reader_available else "complete")
    )
    return {
        "status": status,
        "old_count": len(old_files),
        "new_count": len(new_files),
        "exact_matches": exact_matches,
        "candidates": candidates,
        "unmatched_old": unmatched_old_paths,
        "unmatched_new": unmatched_new_paths,
        "issues": issues,
        "reader": {"available": reader_available, "required": needs_geometry},
    }


def _validate_folder(path: Path, side: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise AppError(
            "CATPART_FOLDER_NOT_FOUND",
            "Le dossier CATPart n'existe pas ou est inaccessible.",
            status_code=404,
            detail={"side": side},
        ) from exc
    if not resolved.is_dir():
        raise AppError(
            "CATPART_FOLDER_NOT_DIR",
            "Le chemin selectionne n'est pas un dossier.",
            status_code=400,
            detail={"side": side},
        )
    return resolved


def _scan_folder(root: Path, side: str) -> list[CatPartFile]:
    files: list[CatPartFile] = []

    def _walk_error(exc: OSError) -> None:
        raise AppError(
            "CATPART_FOLDER_READ_FAILED",
            "Lecture du dossier CATPart impossible.",
            status_code=400,
            detail={"side": side},
        ) from exc

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False, onerror=_walk_error):
        current = Path(dirpath)
        dirnames[:] = [name for name in sorted(dirnames) if not (current / name).is_symlink()]
        for name in sorted(filenames):
            path = current / name
            if path.suffix.lower() != ".catpart" or path.is_symlink():
                continue
            if len(files) >= MAX_CATPART_FILES_PER_FOLDER:
                raise AppError(
                    "CATPART_LIMIT_EXCEEDED",
                    f"Le prototype accepte au maximum {MAX_CATPART_FILES_PER_FOLDER} fichiers CATPart "
                    "par dossier.",
                    status_code=413,
                    detail={"side": side, "max_files": MAX_CATPART_FILES_PER_FOLDER},
                )
            relative_path = path.relative_to(root).as_posix()
            try:
                digest = _sha256_file(path)
            except OSError as exc:
                raise AppError(
                    "CATPART_READ_FAILED",
                    "Lecture d'un fichier CATPart impossible.",
                    status_code=400,
                    detail={"file": relative_path},
                ) from exc
            files.append(CatPartFile(path, relative_path, digest))
    return sorted(files, key=lambda item: item.relative_path.casefold())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _group_by_hash(files: list[CatPartFile]) -> dict[str, list[CatPartFile]]:
    groups: dict[str, list[CatPartFile]] = defaultdict(list)
    for item in files:
        groups[item.sha256].append(item)
    return groups


def _build_candidates(
    old_files: list[CatPartFile],
    new_files: list[CatPartFile],
    signatures: dict[Path, GeometrySignature],
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for old_file in old_files:
        old_signature = signatures.get(old_file.absolute_path)
        if old_signature is None:
            continue
        scored: list[tuple[CatPartFile, float]] = []
        for new_file in new_files:
            new_signature = signatures.get(new_file.absolute_path)
            if new_signature is None:
                continue
            score = geometry_similarity(old_signature, new_signature)
            if score >= _MIN_CANDIDATE_SIMILARITY:
                scored.append((new_file, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].relative_path.casefold()))
        for new_file, score in scored[:_MAX_CANDIDATES_PER_FILE]:
            candidates.append(
                {
                    "old_file": old_file.relative_path,
                    "new_file": new_file.relative_path,
                    "similarity": score,
                    "confidence": "low",
                    "old_geometry_quality": old_signature.quality,
                    "new_geometry_quality": signatures[new_file.absolute_path].quality,
                    "binary_equal": old_file.sha256 == new_file.sha256,
                }
            )
    return candidates


def _issue_dict(file: str | None, issue: GeometryIssue) -> dict[str, str | None]:
    return {"file": file, "code": issue.code, "message": issue.message}
