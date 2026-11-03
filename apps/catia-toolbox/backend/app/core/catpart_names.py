"""CATPart filename scanning and flexible GE identifier parsing."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import AppError

MAX_CATPART_FILES_PER_FOLDER = 20_000
_GE_MARKER = re.compile(r"(?<![A-Z0-9])GE(?![A-Z0-9])", re.IGNORECASE)
_GE_IDENTIFIER = re.compile(
    r"(?<![A-Z0-9])GE[_-]+(?:[A-Z0-9][_-]+)?"
    r"(?P<sin>[A-Z0-9]{5})[_-]+(?P<pn>[A-Z0-9]+)(?=$|[^A-Z0-9])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CatPartFile:
    relative_path: str
    filename: str


@dataclass(frozen=True)
class GeCatPart:
    relative_path: str
    sin: str
    pn: str


def scan_catpart_folder(root: Path, side: str) -> list[CatPartFile]:
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
                path.stat(follow_symlinks=False)
            except OSError as exc:
                raise AppError(
                    "CATPART_READ_FAILED",
                    "Lecture d'un fichier CATPart impossible.",
                    status_code=400,
                    detail={"side": side, "file": relative_path},
                ) from exc
            files.append(CatPartFile(relative_path=relative_path, filename=name))
    return sorted(files, key=lambda item: item.relative_path.casefold())


def parse_ge_files(
    files: list[CatPartFile],
) -> tuple[list[GeCatPart], list[dict[str, str | None]]]:
    ge_files: list[GeCatPart] = []
    issues: list[dict[str, str | None]] = []
    for item in files:
        stem = Path(item.filename).stem
        matches = list(_GE_IDENTIFIER.finditer(stem))
        if len(matches) == 1:
            match = matches[0]
            ge_files.append(
                GeCatPart(
                    relative_path=item.relative_path,
                    sin=match.group("sin"),
                    pn=match.group("pn"),
                )
            )
        elif matches or _GE_MARKER.search(stem):
            issues.append(
                {
                    "file": item.relative_path,
                    "code": "GE_FILENAME_AMBIGUOUS" if matches else "GE_FILENAME_INVALID",
                    "message": (
                        "Plusieurs identifiants GE ont ete detectes dans ce nom."
                        if matches
                        else "Identifiant GE invalide; SIN de 5 caracteres et PN alphanumerique attendus."
                    ),
                }
            )
    return ge_files, issues
