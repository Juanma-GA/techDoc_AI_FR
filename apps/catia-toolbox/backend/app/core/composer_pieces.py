from __future__ import annotations

import os
import shutil
from pathlib import Path

from app.core.errors import AppError
from app.core.security import safe_under_root

_PIECE_EXTENSIONS = frozenset({".smggeom", ".smgxml"})
_LOCAL_BIND_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def resolve_piece_folder_path(
    input_root: str,
    path: str,
    bind_host: str,
    *,
    invalid_path_code: str,
    invalid_path_message: str,
) -> Path:
    if input_root.strip():
        return safe_under_root(input_root, path)
    if bind_host.strip().lower() not in _LOCAL_BIND_HOSTS:
        raise AppError(
            "ROOT_NOT_CONFIGURED",
            "Configurez une racine Input avant d'utiliser ce traitement sur un serveur distant.",
            status_code=400,
        )

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise AppError(invalid_path_code, invalid_path_message, status_code=400)
    return candidate.resolve()


def list_composer_piece_files(folder: Path) -> list[Path]:
    return _scan_composer_piece_folder(folder, strict=True)


def find_composer_piece_files(folder: Path) -> list[Path]:
    return _scan_composer_piece_folder(folder, strict=False)


def _scan_composer_piece_folder(folder: Path, *, strict: bool) -> list[Path]:
    if not folder.is_dir():
        raise NotADirectoryError(str(folder))

    files: list[Path] = []
    invalid_entries: list[str] = []
    with os.scandir(folder) as entries:
        for entry in entries:
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                if strict:
                    invalid_entries.append(entry.name)
                continue
            if Path(entry.name).suffix.casefold() not in _PIECE_EXTENSIONS:
                if strict:
                    invalid_entries.append(entry.name)
                continue
            files.append(Path(entry.path))

    if invalid_entries:
        raise AppError(
            "PIECES_FOLDER_CONTENT_INVALID",
            (
                "Le dossier doit contenir uniquement des fichiers .smgGeom et .smgXml, "
                "sans sous-dossiers ni autres fichiers."
            ),
            status_code=400,
            detail={
                "entries": sorted(invalid_entries, key=str.casefold)[:50],
                "total_invalid": len(invalid_entries),
            },
        )
    return sorted(files, key=lambda path: path.name.casefold())


def copy_composer_pieces_to_workspace(source: Path) -> Path:
    files = find_composer_piece_files(source)
    source = source.resolve()
    base_name = f"{source.name}_optimized"
    output = _create_unique_folder(source, base_name)
    try:
        for piece in files:
            shutil.copy2(piece, output / piece.name)
        list_composer_piece_files(output)
    except (OSError, AppError) as copy_error:
        try:
            shutil.rmtree(output)
        except OSError as cleanup_error:
            raise OSError(
                f"Workspace creation failed ({copy_error}); partial output cleanup failed ({cleanup_error})."
            ) from copy_error
        raise
    return output


def _create_unique_folder(parent: Path, base_name: str) -> Path:
    index = 1
    while True:
        suffix = "" if index == 1 else f"_{index}"
        candidate = parent / f"{base_name}{suffix}"
        try:
            candidate.mkdir()
        except FileExistsError:
            index += 1
            continue
        return candidate
