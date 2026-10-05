from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import fitz

from app.core.errors import AppError


FIELD_ALIASES = {
    "reference": {
        "reference",
        "ref",
        "ecn",
        "ecn ref",
        "ecn reference",
        "document reference",
        "document number",
    },
    "revision": {"revision", "revision number", "revision @", "rev", "rev number"},
    "subject": {"subject", "sujet", "objet", "ecn subject"},
    "title": {"title", "titre", "ecn title"},
    "author": {"author", "auteur", "originator", "prepared by", "created by"},
    "response_required": {
        "response required",
        "response requested",
        "requires response",
        "answer required",
        "reponse requise",
        "reponse demandee",
        "reponse attendue",
    },
    "module_3_open_actions": {
        "module 3",
        "module 3 action ouvertes",
        "module 3 actions",
        "module 3 actions ouvertes",
        "module 3 open actions",
        "open actions",
        "actions ouvertes",
        "actions ouvertes module 3",
    },
}
ALIAS_TO_FIELD = {alias: field for field, aliases in FIELD_ALIASES.items() for alias in aliases}
REFERENCE_PATTERN = re.compile(
    r"\bGKN-[A-Z0-9]+(?:[-_/][A-Z0-9]+)*(?:@[A-Z0-9][A-Z0-9._-]*)?\b",
    re.I,
)
LABEL_VALUE_PATTERN = re.compile(r"^\s*(?P<label>[^:\t]{1,80}?)\s*(?::|\t)\s*(?P<value>.*?)\s*$")


def normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9@]+", " ", ascii_value).strip()


def field_for_label(label: str) -> str | None:
    return ALIAS_TO_FIELD.get(normalize_label(label))


def list_pdf_files(source: Path) -> list[Path]:
    if source.is_file():
        if source.suffix.casefold() != ".pdf":
            raise AppError("INVALID_PDF_SOURCE", "Le fichier sélectionné doit être un PDF.")
        return [source]
    if not source.is_dir():
        raise AppError("INVALID_PDF_SOURCE", "La source doit être un PDF ou un dossier.")
    files = sorted(
        (path.resolve() for path in source.iterdir() if path.is_file() and path.suffix.casefold() == ".pdf"),
        key=lambda path: path.name.casefold(),
    )
    if not files:
        raise AppError("NO_PDFS", "Aucun PDF trouvé directement dans le dossier sélectionné.")
    return files


def read_pdf_text(path: Path) -> str:
    try:
        document = fitz.open(path)
        try:
            if document.needs_pass:
                raise AppError(
                    "PDF_PASSWORD_PROTECTED",
                    f"Le PDF {path.name} est protégé par mot de passe.",
                )
            text = "\n".join(page.get_text("text") for page in document)
        finally:
            document.close()
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AppError("INVALID_PDF", f"Impossible de lire le PDF {path.name}.") from exc

    text = text.replace("\u00a0", " ").replace("\u2007", " ").replace("\u202f", " ")
    if not text.strip():
        raise AppError(
            "PDF_HAS_NO_TEXT",
            f"Le PDF {path.name} ne contient pas de texte sélectionnable. L'OCR n'est pas activé.",
        )
    return text


def extract_fields(text: str) -> tuple[dict[str, str], dict[str, str]]:
    fields = {field: "" for field in FIELD_ALIASES}
    label_values: dict[str, str] = {}
    for line in text.splitlines():
        match = LABEL_VALUE_PATTERN.match(line)
        if not match:
            continue
        label = match.group("label").strip()
        value = match.group("value").strip()
        if not value:
            continue
        normalized_label = normalize_label(label)
        label_values.setdefault(normalized_label, value)
        field = ALIAS_TO_FIELD.get(normalized_label)
        if field and not fields[field]:
            fields[field] = value

    if not fields["reference"]:
        match = REFERENCE_PATTERN.search(text)
        if match:
            fields["reference"] = match.group(0)

    reference = fields["reference"]
    if "@" in reference:
        base_reference, revision_suffix = reference.rsplit("@", 1)
        if base_reference.strip() and revision_suffix.strip():
            fields["reference"] = base_reference.strip()
            if not fields["revision"]:
                fields["revision"] = f"@{revision_suffix.strip()}"

    if not fields["subject"]:
        fields["subject"] = fields["title"]
    return fields, label_values


def column_values(
    columns: list[dict[str, Any]],
    fields: dict[str, str],
    labels: dict[str, str],
) -> list[str]:
    values: list[str] = []
    for column in columns:
        field = field_for_label(column["name"])
        value = fields.get(field, "") if field else labels.get(normalize_label(column["name"]), "")
        values.append(value)
    return values