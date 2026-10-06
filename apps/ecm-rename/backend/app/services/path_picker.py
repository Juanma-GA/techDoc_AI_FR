from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

from app.core.errors import AppError

BrowseKind = Literal["source_files", "source_directory", "tracker_file", "output_directory"]
BrowseLanguage = Literal["fr", "en"]

_TITLES: dict[BrowseKind, dict[BrowseLanguage, str]] = {
    "source_files": {"fr": "Sélectionner des PDF", "en": "Select PDFs"},
    "source_directory": {"fr": "Sélectionner le dossier source", "en": "Select the source folder"},
    "tracker_file": {"fr": "Sélectionner le tracker Excel", "en": "Select the Excel tracker"},
    "output_directory": {"fr": "Sélectionner le dossier de sortie", "en": "Select the output folder"},
}
_FILE_FILTERS: dict[BrowseKind, dict[BrowseLanguage, str]] = {
    "source_files": {
        "fr": "Fichiers PDF (*.pdf)|*.pdf|Tous les fichiers (*.*)|*.*",
        "en": "PDF files (*.pdf)|*.pdf|All files (*.*)|*.*",
    },
    "tracker_file": {
        "fr": "Fichiers Excel (*.xlsx;*.xlsm)|*.xlsx;*.xlsm|Tous les fichiers (*.*)|*.*",
        "en": "Excel files (*.xlsx;*.xlsm)|*.xlsx;*.xlsm|All files (*.*)|*.*",
    },
}

_WINDOWS_PICKER_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
Add-Type -AssemblyName System.Windows.Forms
$kind = $env:ECM_RENAME_PICKER_KIND
$title = $env:ECM_RENAME_PICKER_TITLE
$initialDirectory = $env:ECM_RENAME_PICKER_INITIAL_DIRECTORY

if ($kind -eq 'source_files' -or $kind -eq 'tracker_file') {
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = $title
    $dialog.Filter = $env:ECM_RENAME_PICKER_FILTER
    $dialog.Multiselect = ($kind -eq 'source_files')
    if ($initialDirectory -and (Test-Path -LiteralPath $initialDirectory -PathType Container)) {
        $dialog.InitialDirectory = $initialDirectory
    }
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        if ($kind -eq 'source_files') {
            $dialog.FileNames | ForEach-Object { [Console]::WriteLine($_) }
        } else {
            [Console]::WriteLine($dialog.FileName)
        }
    }
    $dialog.Dispose()
    exit 0
}

$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = $title
$dialog.ShowNewFolderButton = ($kind -eq 'output_directory')
if ($initialDirectory -and (Test-Path -LiteralPath $initialDirectory -PathType Container)) {
    $dialog.SelectedPath = $initialDirectory
}
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::WriteLine($dialog.SelectedPath)
}
$dialog.Dispose()
"""


def _initial_directory(value: str | None) -> str | None:
    if not value:
        return None
    try:
        first_path = next((line.strip() for line in value.splitlines() if line.strip()), value)
        path = Path(os.path.expandvars(first_path.strip().strip('"'))).expanduser()
        if path.is_file() or not path.exists():
            path = path.parent
        return str(path) if path.is_dir() else None
    except (OSError, RuntimeError, ValueError):
        return None


def _is_windows_runtime() -> bool:
    return os.name == "nt"


def _pick_with_windows(
    kind: BrowseKind,
    title: str,
    language: BrowseLanguage,
    initial_directory: str | None,
) -> list[str] | None:
    executable = shutil.which("powershell.exe") or shutil.which("powershell")
    if not executable:
        raise AppError(
            "PATH_PICKER_UNAVAILABLE",
            "PowerShell n'est pas disponible pour ouvrir le sélecteur de fichiers.",
            status_code=503,
        )

    environment = {
        key: value
        for key, value in os.environ.items()
        if key.casefold() in {"path", "systemroot", "windir", "temp", "tmp", "userprofile"}
    }
    environment.update(
        {
            "ECM_RENAME_PICKER_KIND": kind,
            "ECM_RENAME_PICKER_TITLE": title,
            "ECM_RENAME_PICKER_FILTER": _FILE_FILTERS.get(kind, {}).get(language, ""),
            "ECM_RENAME_PICKER_INITIAL_DIRECTORY": initial_directory or "",
        }
    )
    command = [
        executable,
        "-NoProfile",
        "-NonInteractive",
        "-STA",
        "-WindowStyle",
        "Hidden",
        "-Command",
        _WINDOWS_PICKER_SCRIPT,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except OSError as exc:
        raise AppError(
            "PATH_PICKER_UNAVAILABLE",
            "Impossible d'ouvrir le sélecteur de fichiers.",
            status_code=503,
        ) from exc
    if result.returncode != 0:
        raise AppError(
            "PATH_PICKER_UNAVAILABLE",
            "Impossible d'ouvrir le sélecteur de fichiers.",
            status_code=503,
        )
    selected_paths = [line for line in result.stdout.splitlines() if line]
    return selected_paths or None


def _pick_with_tk(
    kind: BrowseKind,
    title: str,
    language: BrowseLanguage,
    initial_directory: str | None,
) -> list[str] | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise AppError(
            "PATH_PICKER_UNAVAILABLE",
            "Le sélecteur de fichiers n'est pas disponible sur cet environnement.",
            status_code=503,
        ) from exc

    options: dict[str, Any] = {"title": title}
    if initial_directory:
        options["initialdir"] = initial_directory
    root: tk.Tk | None = None
    selected_path = ""
    selected_paths: tuple[str, ...] = ()
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        options["parent"] = root
        if kind == "source_files":
            file_label = "PDF files" if language == "en" else "Fichiers PDF"
            all_label = "All files" if language == "en" else "Tous les fichiers"
            selected_paths = filedialog.askopenfilenames(
                **options,
                filetypes=((file_label, "*.pdf"), (all_label, "*.*")),
            )
        elif kind == "tracker_file":
            excel_label = "Excel files" if language == "en" else "Fichiers Excel"
            all_label = "All files" if language == "en" else "Tous les fichiers"
            selected_path = filedialog.askopenfilename(
                **options,
                filetypes=((excel_label, ("*.xlsx", "*.xlsm")), (all_label, "*.*")),
            )
        else:
            selected_path = filedialog.askdirectory(
                **options,
                mustexist=kind == "source_directory",
            )
    except tk.TclError as exc:
        raise AppError(
            "PATH_PICKER_UNAVAILABLE",
            "Impossible d'ouvrir le sélecteur de fichiers.",
            status_code=503,
        ) from exc
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
    if kind == "source_files":
        return list(selected_paths) or None
    return [selected_path] if selected_path else None


def choose_path(kind: BrowseKind, current_path: str | None, language: BrowseLanguage) -> list[str] | None:
    title = _TITLES[kind][language]
    initial_directory = _initial_directory(current_path)
    if _is_windows_runtime():
        return _pick_with_windows(kind, title, language, initial_directory)
    return _pick_with_tk(kind, title, language, initial_directory)
