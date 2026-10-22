from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from zipfile import BadZipFile

from app.core.errors import AppError

INFO_CODE_REFERENCE_PATH = Path(__file__).resolve().parents[3] / "S1000D_4.1_info_codes.xlsx"

_SCHEMA_TO_DM_TYPE = {
    "descript": "descriptive",
    "proced": "procedural",
    "ipd": "ipd",
}


def normalize_info_code(value: object) -> str:
    if value is None or isinstance(value, bool):
        return ""
    code = re.sub(r"\s+", "", str(value).strip().upper())
    numeric = re.fullmatch(r"(\d{1,3})(?:\.0+)?", code)
    if numeric:
        return numeric.group(1).zfill(3)
    variant = re.fullmatch(r"(\d{3})[A-Z]", code)
    return variant.group(1) if variant else code


def _normalize_header(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_schema(value: object) -> str:
    return re.sub(r"\s+", "", _normalize_header(value))


def dm_type_for_schema(schema: str) -> str | None:
    return _SCHEMA_TO_DM_TYPE.get(normalize_schema(schema))


def load_info_code_schemas(path: str | Path | None = None) -> dict[str, str]:
    reference_path = Path(path) if path is not None else INFO_CODE_REFERENCE_PATH
    if not reference_path.is_file():
        raise AppError(
            "INFO_CODE_MAP_NOT_FOUND",
            f"Fichier de correspondance InfoCode introuvable : {reference_path.name}.",
            503,
        )

    try:
        from openpyxl import load_workbook
        from openpyxl.utils.exceptions import InvalidFileException
    except ImportError as exc:  # pragma: no cover - dependency is declared by the backend
        raise AppError(
            "INFO_CODE_MAP_UNAVAILABLE",
            "Lecture du fichier de correspondance InfoCode indisponible : openpyxl n'est pas installe.",
            503,
        ) from exc

    try:
        workbook = load_workbook(reference_path, read_only=True, data_only=True)
    except (InvalidFileException, BadZipFile, OSError, ValueError) as exc:
        raise AppError(
            "INFO_CODE_MAP_INVALID",
            f"Impossible de lire le fichier de correspondance InfoCode : {exc}.",
            503,
        ) from exc

    try:
        worksheet = workbook.active
        header = next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if not header:
            raise AppError(
                "INFO_CODE_MAP_INVALID",
                "Le fichier de correspondance InfoCode ne contient pas d'en-tete.",
                503,
            )

        columns = {
            _normalize_header(value): index
            for index, value in enumerate(header)
            if value is not None
        }
        code_column = next(
            (columns[name] for name in ("info code", "infocode") if name in columns),
            None,
        )
        schema_column = next(
            (
                columns[name]
                for name in ("schema recommande", "recommended schema")
                if name in columns
            ),
            None,
        )
        if code_column is None or schema_column is None:
            raise AppError(
                "INFO_CODE_MAP_INVALID",
                "Le fichier doit contenir les colonnes « Info code » et « Schéma recommandé ».",
                503,
            )

        schemas: dict[str, str] = {}
        for row_number, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
            code = normalize_info_code(row[code_column] if code_column < len(row) else None)
            schema = normalize_schema(row[schema_column] if schema_column < len(row) else None)
            if not code and not schema:
                continue
            if not code or not schema:
                raise AppError(
                    "INFO_CODE_MAP_INVALID",
                    f"Valeur InfoCode ou schéma manquante à la ligne {row_number} du fichier.",
                    503,
                )
            if code in schemas and schemas[code] != schema:
                raise AppError(
                    "INFO_CODE_MAP_INVALID",
                    f"Correspondances contradictoires pour l'InfoCode {code}.",
                    503,
                )
            schemas[code] = schema
        if not schemas:
            raise AppError(
                "INFO_CODE_MAP_INVALID",
                "Le fichier de correspondance InfoCode ne contient aucune correspondance.",
                503,
            )
        return schemas
    finally:
        workbook.close()
