"""Detection and execution helpers for CATIA Composer Converter."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AppConfig

_EXECUTABLE_KEY = "composer_converter_path"
_SETTINGS_KEY = "composer_settings_path"
_EXECUTABLE_NAME = "ComposerConverter.exe"


@dataclass(frozen=True)
class ComposerConverterStatus:
    available: bool
    executable: str
    settings_file: str
    version: str
    message: str


@dataclass(frozen=True)
class ComposerConversionResult:
    returncode: int
    stdout: str
    stderr: str
    converted: int
    failed: int


def _get_config(db: Session, key: str) -> str:
    row = db.get(AppConfig, key)
    return row.value.strip() if row and row.value else ""


def _set_config(db: Session, key: str, value: str) -> str:
    cleaned = (value or "").strip()[:2000]
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=cleaned))
    else:
        row.value = cleaned
    return cleaned


def get_converter_path(db: Session) -> str:
    return _get_config(db, _EXECUTABLE_KEY)


def get_settings_path(db: Session) -> str:
    return _get_config(db, _SETTINGS_KEY)


def set_paths(db: Session, *, executable: str | None = None, settings_file: str | None = None) -> None:
    if executable is not None:
        _set_config(db, _EXECUTABLE_KEY, executable)
    if settings_file is not None:
        _set_config(db, _SETTINGS_KEY, settings_file)
    db.commit()


def _version_from_path(path: Path) -> str:
    parts = path.parts
    try:
        composer_index = parts.index("CATIAComposer")
        return parts[composer_index + 1]
    except (ValueError, IndexError):
        return ""


def _version_key(path: Path) -> tuple[int, ...]:
    version = _version_from_path(path)
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return ()


def detect_executable(configured: str = "") -> Path | None:
    if configured:
        path = Path(configured).expanduser()
        return path.resolve() if path.is_file() else None
    if sys.platform != "win32":
        return None

    env_path = os.environ.get("CATIA_COMPOSER_CONVERTER", "").strip()
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path).expanduser())

    program_files = [os.environ.get("ProgramFiles", r"C:\Program Files")]
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    if program_files_x86:
        program_files.append(program_files_x86)
    for root in program_files:
        install_root = Path(root) / "Dassault Systemes" / "CATIAComposer"
        if install_root.is_dir():
            candidates.extend(
                sorted(install_root.glob(r"*\Bin\ComposerConverter.exe"), key=_version_key, reverse=True)
            )

    on_path = shutil.which(_EXECUTABLE_NAME)
    if on_path:
        candidates.append(Path(on_path))
    return next((path.resolve() for path in candidates if path.is_file()), None)


def get_status(db: Session) -> ComposerConverterStatus:
    configured_executable = get_converter_path(db)
    executable = detect_executable(configured_executable)
    settings_value = get_settings_path(db)
    settings_file = Path(settings_value).expanduser() if settings_value else None

    if configured_executable and executable is None:
        return ComposerConverterStatus(
            False,
            configured_executable,
            settings_value,
            "",
            "Le chemin configure vers ComposerConverter.exe est introuvable.",
        )
    if executable is None:
        return ComposerConverterStatus(
            False,
            "",
            settings_value,
            "",
            "CATIA Composer Converter est introuvable sur ce poste.",
        )
    if settings_file is None:
        return ComposerConverterStatus(
            False,
            str(executable),
            "",
            _version_from_path(executable),
            "Selectionnez un profil XML exporte depuis CATIA Composer Converter.",
        )
    if not settings_file.is_file() or settings_file.suffix.lower() != ".xml":
        return ComposerConverterStatus(
            False,
            str(executable),
            settings_value,
            _version_from_path(executable),
            "Le profil de conversion Composer doit etre un fichier XML existant.",
        )
    return ComposerConverterStatus(
        True,
        str(executable),
        str(settings_file.resolve()),
        _version_from_path(executable),
        "CATIA Composer Converter est pret.",
    )


def build_command(status: ComposerConverterStatus, source: Path) -> list[str]:
    if not status.available:
        raise ValueError(status.message)
    return [status.executable, str(source), status.settings_file]


def output_candidates(source: Path, target: Path) -> list[Path]:
    return [
        target,
        source.with_suffix(".smgXml"),
        source.with_suffix(".smgxml"),
        source.with_suffix(".smg"),
        target.with_suffix(".smgXml"),
        target.with_suffix(".smg"),
    ]


def snapshot_outputs(source: Path, target: Path) -> dict[Path, tuple[int, int]]:
    return {
        path: (path.stat().st_mtime_ns, path.stat().st_size)
        for path in output_candidates(source, target)
        if path.is_file()
    }


def find_generated_file(
    source: Path,
    target: Path,
    previous: dict[Path, tuple[int, int]] | None = None,
) -> Path | None:
    for path in output_candidates(source, target):
        if not path.is_file():
            continue
        signature = (path.stat().st_mtime_ns, path.stat().st_size)
        if previous is None or previous.get(path) != signature:
            return path
    return None


def execute_plan(
    items: Iterable[Any],
    *,
    base: str,
    status: ComposerConverterStatus,
    dry_run: bool,
    env: dict[str, str],
    timeout: int,
) -> ComposerConversionResult:
    stdout = ["DRY_RUN=True" if dry_run else "DRY_RUN=False"]
    stderr: list[str] = []
    converted = 0
    failed = 0
    base_path = Path(base).resolve() if base else None

    for item in items:
        source = Path(base, item.source_path.replace("/", os.sep)).resolve()
        target = Path(base, item.target_path.replace("/", os.sep)).resolve()
        if base_path is not None and (
            not source.is_relative_to(base_path) or not target.is_relative_to(base_path)
        ):
            failed += 1
            stderr.append(f"Chemin hors de la racine autorisee: {item.source_path}")
            continue
        if not source.is_file():
            failed += 1
            stderr.append(f"Source introuvable: {source}")
            continue

        command = (
            build_command(status, source)
            if not dry_run
            else [status.executable or _EXECUTABLE_NAME, str(source), status.settings_file or "<profil.xml>"]
        )
        stdout.append(f"[{'TEST' if dry_run else 'CONVERSION'}] {' '.join(command)}")
        if dry_run:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        previous_outputs = snapshot_outputs(source, target)
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=target.parent,
        )
        if proc.stdout:
            stdout.append(proc.stdout.strip())
        if proc.stderr:
            stderr.append(proc.stderr.strip())

        generated = find_generated_file(source, target, previous_outputs)
        if proc.returncode != 0 or generated is None:
            failed += 1
            if proc.returncode != 0:
                stderr.append(f"Composer Converter a retourne le code {proc.returncode} pour {source.name}.")
            if generated is None:
                stderr.append(f"Composer n'a genere aucun fichier pour {source.name}.")
            continue
        if generated != target:
            if target.exists():
                failed += 1
                stderr.append(f"La cible existe deja, fichier conserve: {target}")
                continue
            shutil.move(str(generated), str(target))
        converted += 1

    return ComposerConversionResult(
        returncode=0 if dry_run or failed == 0 else 1,
        stdout="\n".join(stdout)[-20000:],
        stderr="\n".join(stderr)[-20000:],
        converted=converted,
        failed=failed,
    )
