from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.services.ecm_rename_pdf import column_values, extract_fields, list_pdf_files, read_pdf_text
from app.services.ecm_rename_tracker_3 import (
    append_tracker_rows,
    find_tracker_layout,
    open_tracker,
    save_tracker,
)

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _app_error(code: str, message: str, status_code: int = 400) -> AppError:
    return AppError(code=code, message=message, status_code=status_code)


def _user_path(value: str, label: str, *, must_exist: bool) -> Path:
    cleaned = value.strip().strip('"')
    if not cleaned:
        raise _app_error("INVALID_PATH", f"{label} ne peut pas être vide.")
    expanded = os.path.expandvars(cleaned)
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        raise _app_error("INVALID_PATH", f"{label} doit être un chemin absolu.")
    try:
        return path.resolve(strict=must_exist)
    except (OSError, RuntimeError) as exc:
        raise _app_error("PATH_NOT_FOUND", f"{label} est introuvable ou inaccessible.") from exc


def _tracker_path(value: str, *, must_exist: bool) -> Path:
    path = _user_path(value, "Le tracker Excel", must_exist=must_exist)
    if path.suffix.casefold() not in {".xlsx", ".xlsm"}:
        raise _app_error("UNSUPPORTED_TRACKER", "Le tracker doit être au format .xlsx ou .xlsm.")
    if must_exist and not path.is_file():
        raise _app_error("TRACKER_NOT_FOUND", "Le tracker Excel sélectionné est introuvable.")
    return path


def preview_batch(
    source_path: str,
    tracker_path: str,
    sheet_name: str | None = None,
    header_row: int | None = None,
) -> dict[str, Any]:
    source = _user_path(source_path, "La source PDF", must_exist=True)
    tracker = _tracker_path(tracker_path, must_exist=True)
    files = list_pdf_files(source)
    with open_tracker(tracker, read_only=True) as workbook:
        sheet, selected_header_row, columns = find_tracker_layout(workbook, sheet_name, header_row)
        records = []
        for pdf_path in files:
            text = read_pdf_text(pdf_path)
            fields, labels = extract_fields(text)
            records.append(
                {
                    "source_path": str(pdf_path),
                    "file_name": pdf_path.name,
                    "reference": fields["reference"],
                    "revision": fields["revision"],
                    "subject": fields["subject"],
                    "tracker_values": column_values(columns, fields, labels),
                }
            )
        return {
            "source_path": str(source),
            "tracker_path": str(tracker),
            "sheet_names": [item.name for item in workbook.sheets],
            "sheet_name": sheet.name,
            "header_row": selected_header_row,
            "columns": columns,
            "records": records,
        }


def _safe_folder_name(reference: str, revision: str, subject: str) -> str:
    raw_name = "-".join(part.strip() for part in (reference, revision, subject) if part.strip())
    safe_name = INVALID_FILENAME_CHARS.sub("_", raw_name).rstrip(" .")
    safe_name = re.sub(r"\s+", " ", safe_name)
    if not reference.strip() or not subject.strip() or not safe_name:
        raise _app_error(
            "MISSING_FOLDER_METADATA",
            "La référence et le sujet sont requis pour créer le dossier.",
        )
    if len(safe_name) > 180:
        raise _app_error(
            "FOLDER_NAME_TOO_LONG",
            "Le nom de dossier dépasse 180 caractères. Raccourcis le sujet.",
        )
    return safe_name


def create_folders_batch(
    source_path: str,
    output_path: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    source = _user_path(source_path, "La source PDF", must_exist=True)
    output = _user_path(output_path, "Le dossier de sortie", must_exist=False)
    if output.exists() and not output.is_dir():
        raise _app_error("INVALID_OUTPUT", "Le chemin de sortie existe mais n'est pas un dossier.")
    if source.is_dir() and output == source:
        raise _app_error(
            "INVALID_OUTPUT",
            "Choisis un dossier de sortie différent du dossier source des PDF.",
        )

    files = list_pdf_files(source)
    file_by_path = {str(path.resolve()): path for path in files}
    record_paths = [str(Path(record["source_path"]).resolve()) for record in records]
    if len(record_paths) != len(set(record_paths)) or set(record_paths) != set(file_by_path):
        raise _app_error(
            "STALE_PREVIEW",
            "La liste des PDF a changé. Relance l'analyse avant la création des dossiers.",
        )

    folder_names: list[str] = []
    for record in records:
        folder_names.append(_safe_folder_name(record["reference"], record["revision"], record["subject"]))
    if len({name.casefold() for name in folder_names}) != len(folder_names):
        raise _app_error("DUPLICATE_FOLDER", "Plusieurs PDF produiraient le même nom de dossier.")
    destinations = [output / name for name in folder_names]
    conflicts = [path.name for path in destinations if path.exists() and not path.is_dir()]
    if conflicts:
        raise _app_error("OUTPUT_EXISTS", f"Un élément de sortie n'est pas un dossier : {', '.join(conflicts)}", 409)

    pending_folders = [
        (record, folder_name, destination)
        for record, folder_name, destination in zip(records, folder_names, destinations, strict=True)
        if not destination.is_dir()
    ]
    existing_folders = [str(path) for path in destinations if path.is_dir()]

    stage_root: Path | None = None
    created_destinations: list[Path] = []
    try:
        if pending_folders:
            output.mkdir(parents=True, exist_ok=True)
            stage_root = Path(tempfile.mkdtemp(prefix=".ecm-rename-", dir=output))
            for record, folder_name, _ in pending_folders:
                source_file = file_by_path[str(Path(record["source_path"]).resolve())]
                staged_folder = stage_root / folder_name
                staged_folder.mkdir()
                shutil.copy2(source_file, staged_folder / source_file.name)

            for _, folder_name, destination in pending_folders:
                os.replace(stage_root / folder_name, destination)
                created_destinations.append(destination)

        return {
            "created_folders": [str(destination) for _, _, destination in pending_folders],
            "existing_folders": existing_folders,
        }
    except AppError:
        for destination in created_destinations:
            shutil.rmtree(destination, ignore_errors=True)
        raise
    except Exception as exc:
        for destination in created_destinations:
            shutil.rmtree(destination, ignore_errors=True)
        raise _app_error(
            "FOLDERS_FAILED",
            "La création des dossiers a échoué. Vérifie les droits sur les dossiers source et sortie.",
            500,
        ) from exc
    finally:
        if stage_root is not None:
            shutil.rmtree(stage_root, ignore_errors=True)


def append_tracker_batch(
    tracker_path: str,
    sheet_name: str,
    header_row: int,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    tracker = _tracker_path(tracker_path, must_exist=True)
    stat_before = tracker.stat()
    try:
        with open_tracker(tracker, read_only=False) as workbook:
            sheet, selected_header_row, columns = find_tracker_layout(workbook, sheet_name, header_row)
            if any(len(record["tracker_values"]) != len(columns) for record in records):
                raise _app_error("STALE_PREVIEW", "Les colonnes du tracker ont changé. Relance l'analyse.")

            append_tracker_rows(sheet, selected_header_row, columns, records)

            current_stat = tracker.stat()
            if (current_stat.st_mtime_ns, current_stat.st_size) != (stat_before.st_mtime_ns, stat_before.st_size):
                raise _app_error(
                    "TRACKER_CHANGED",
                    "Le tracker a changé pendant l'analyse. Relance l'opération.",
                    409,
                )

            save_tracker(workbook)
            return {"tracker_path": str(tracker), "rows_written": len(records)}
    except AppError:
        raise
    except Exception as exc:
        raise _app_error(
            "TRACKER_FAILED",
            "L'ajout au tracker a échoué. Vérifie que le fichier Excel est fermé et accessible.",
            500,
        ) from exc
