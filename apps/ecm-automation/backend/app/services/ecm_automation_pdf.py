from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import fitz

from app.core.errors import AppError


FIELD_ALIASES = {
    "send_date": {"date d envoi"},
    "reception_week": {"semaine de reception", "reception week"},
    "reference": {
        "reference",
        "ref",
        "ecn",
        "ecn ref",
        "ecn reference",
        "document reference",
        "document number",
        "cm no",
    },
    "revision": {"revision", "revision number", "revision @", "rev", "rev number"},
    "module": {"module"},
    "subject": {"subject", "sujet", "objet", "ecn subject", "description"},
    "title": {"title", "titre", "ecn title"},
    "author": {"author", "auteur", "originator", "prepared by", "created by"},
    "response_required": {
        "response",
        "reponse",
        "response required",
        "response requested",
        "requires response",
        "answer required",
        "reponse requise",
        "reponse demandee",
        "reponse attendue",
    },
    "response_date": {"date de reponse", "response date"},
    "open_action_count": {"nombre d action ouverte", "opened action counter"},
    "module_3_open_actions": {
        "actions",
        "module 3",
        "module 3 action ouvertes",
        "module 3 actions",
        "module 3 actions ouvertes",
        "module 3 open actions",
        "open actions",
        "actions ouvertes",
        "actions ouvertes module 3",
    },
    "distribution": {"diffusion", "distribution"},
    "status": {"statut", "status"},
}
ALIAS_TO_FIELD = {alias: field for field, aliases in FIELD_ALIASES.items() for alias in aliases}
PDF_ALIAS_TO_FIELD = {
    alias: field
    for alias, field in ALIAS_TO_FIELD.items()
    if not (field == "response_required" and alias in {"response", "reponse"})
}
PDF_ALIAS_TO_FIELD["reply req d"] = "response_required"
PDF_ALIAS_TO_FIELD["date req d"] = "response_required_date"
PDF_ALIAS_TO_FIELD["if yes date req d"] = "response_required_date"
RESPONSE_OPTION_PATTERN = re.compile(
    r"\b(?P<option>yes|no|oui|non)\b\s*"
    r"(?P<mark>\u2612|\u2611|\u2610|\u2613|\u2713|\u2714|\[\s*[xX ]\s*\])",
    re.I,
)
CHECKED_RESPONSE_MARKS = {"\u2612", "\u2611", "\u2613", "\u2713", "\u2714", "[x]"}
REFERENCE_PATTERN = re.compile(
    r"\bGKN-[A-Z0-9]+(?:[-_/][A-Z0-9]+)*(?:@[A-Z0-9][A-Z0-9._-]*)?\b",
    re.I,
)
LABEL_VALUE_PATTERN = re.compile(r"^\s*(?P<label>[^:\t]{1,80}?)\s*(?::|\t)\s*(?P<value>.*?)\s*$")


def normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9@]+", " ", ascii_value).strip()


def _label_candidates(label: str) -> list[str]:
    candidates = [normalize_label(label)]
    candidates.extend(normalize_label(part) for part in re.split(r"[\r\n]+", label))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def field_for_label(label: str) -> str | None:
    return next(
        (
            ALIAS_TO_FIELD[candidate]
            for candidate in _label_candidates(label)
            if candidate in ALIAS_TO_FIELD
        ),
        None,
    )


def _pdf_field_for_label(label: str) -> str | None:
    return next(
        (
            PDF_ALIAS_TO_FIELD[candidate]
            for candidate in _label_candidates(label)
            if candidate in PDF_ALIAS_TO_FIELD
        ),
        None,
    )


def _split_known_label_value(line: str) -> tuple[str, str] | None:
    match = LABEL_VALUE_PATTERN.match(line)
    if match:
        return match.group("label").strip(), match.group("value").strip()

    words = line.split()
    for label_end in range(len(words), 0, -1):
        label = " ".join(words[:label_end]).rstrip(":")
        if _pdf_field_for_label(label):
            return label, " ".join(words[label_end:]).strip()
    return None


def _response_checkbox_value(value: str, lines: list[str], line_index: int) -> tuple[bool, str]:
    option_states: dict[str, bool] = {}
    candidates = [value, *lines[line_index + 1 : line_index + 5]]
    for candidate in candidates:
        for match in RESPONSE_OPTION_PATTERN.finditer(candidate):
            option = match.group("option").casefold()
            option = "yes" if option in {"yes", "oui"} else "no"
            mark = match.group("mark").casefold().replace(" ", "")
            option_states[option] = mark in CHECKED_RESPONSE_MARKS
        if {"yes", "no"}.issubset(option_states):
            break

    checked_options = [option for option, checked in option_states.items() if checked]
    if checked_options:
        return True, "Yes" if checked_options[0] == "yes" else "No"
    return bool(option_states), ""


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
    lines = text.splitlines()
    response_required_date = ""
    for line_index, line in enumerate(lines):
        parts = _split_known_label_value(line)
        if not parts:
            continue
        label, value = parts
        field = _pdf_field_for_label(label)
        checkbox_found = False
        if field == "response_required":
            checkbox_found, checkbox_value = _response_checkbox_value(value, lines, line_index)
            if checkbox_found:
                value = checkbox_value
        if not value and not checkbox_found:
            for candidate in lines[line_index + 1 :]:
                candidate = candidate.strip()
                if not candidate:
                    continue
                next_parts = _split_known_label_value(candidate)
                if next_parts and _pdf_field_for_label(next_parts[0]):
                    continue
                value = candidate
                break
        if not value:
            continue
        normalized_label = normalize_label(label)
        label_values.setdefault(normalized_label, value)
        if field == "response_required_date":
            if not response_required_date:
                response_required_date = value
        elif field and not fields[field]:
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
    if fields["response_required"].casefold() == "yes" and not fields["response_date"]:
        fields["response_date"] = response_required_date
    return fields, label_values


def column_values(
    columns: list[dict[str, Any]],
    fields: dict[str, str],
    labels: dict[str, str],
) -> list[str]:
    values: list[str] = []
    for column in columns:
        field = field_for_label(column["name"])
        if field:
            value = fields.get(field, "")
        else:
            value = next(
                (labels[candidate] for candidate in _label_candidates(column["name"]) if candidate in labels),
                "",
            )
        values.append(value)
    return values