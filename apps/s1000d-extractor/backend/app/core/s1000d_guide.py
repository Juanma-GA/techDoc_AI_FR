"""Chargement et normalisation du guide metier S1000D Excel."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from app.core.errors import AppError

DEFAULT_GUIDE_PATH = Path(__file__).resolve().parents[3] / "Balise_S1000D.xlsx"
GUIDE_VERSION = 1

_SHEET_PROFILES = {"Descript": "descriptive", "Proced": "procedural"}
_REQUIRED_COLUMNS = {
    "element",
    "description",
    "example",
    "example_xml",
    "required_attributes",
    "optional_attributes",
}
_HEADER_ALIASES = {
    "balise": "element",
    "description detaillee": "description",
    "exemple": "example",
    "s1000d": "example_xml",
    "attribut obligatoire": "required_attributes",
    "attribut optionnel": "optional_attributes",
}
_XML_TAG = re.compile(r"<\s*([A-Za-z_][A-Za-z0-9_.:-]*)\b")
_VARIANT = re.compile(r"\s*\(([^()]+)\)\s*$")
_ATTRIBUTE = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]*")

_ROLE_BY_ELEMENT = {
    "title": "title",
    "para": "paragraph",
    "levelledPara": "section",
    "randomList": "unordered_list",
    "sequentialList": "ordered_list",
    "listItem": "list_item",
    "warning": "admonition",
    "caution": "admonition",
    "note": "admonition",
    "emphasis": "emphasis",
    "figure": "figure",
    "internalRef": "internal_reference",
    "dmRef": "dm_reference",
    "symbol": "symbol",
    "table": "table",
    "col": "table_column",
    "row": "table_row",
    "entry": "table_entry",
    "preliminaryRqmts": "preliminary_requirements",
    "productionMaintData": "production_maintenance_data",
    "thresholdInterval": "threshold_interval",
    "taskDuration": "task_duration",
    "reqCondGroup": "required_conditions",
    "reqPersons": "required_personnel",
    "reqSupportEquips": "support_equipment",
    "reqSupplies": "supplies",
    "reqSpares": "spare_parts",
    "reqSafety": "safety_requirements",
    "safetyRqmts": "safety_requirements",
    "proceduralStep": "procedure_step",
    "closeRqmts": "closing_requirements",
}


@dataclass(frozen=True)
class GuideIssue:
    code: str
    severity: str
    message: str
    profile: str
    source_sheet: str
    source_row: int
    field: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "profile": self.profile,
            "source_sheet": self.source_sheet,
            "source_row": self.source_row,
            "field": self.field,
        }


@dataclass(frozen=True)
class GuideRule:
    profile: str
    element: str
    components: tuple[str, ...]
    variants: tuple[str, ...]
    business_role: str | None
    allowed_parents: tuple[str, ...] | None
    allowed_children: tuple[str, ...] | None
    required_attributes: tuple[str, ...]
    optional_attributes: tuple[str, ...]
    example_text: str | None
    example_xml: str | None
    description: str | None
    verification_status: str
    confidence: str
    source_sheet: str
    source_row: int
    raw_element: str

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "element": self.element,
            "components": list(self.components),
            "variants": list(self.variants),
            "business_role": self.business_role,
            "allowed_parents": list(self.allowed_parents) if self.allowed_parents is not None else None,
            "allowed_children": list(self.allowed_children) if self.allowed_children is not None else None,
            "required_attributes": list(self.required_attributes),
            "optional_attributes": list(self.optional_attributes),
            "example_text": self.example_text,
            "example_xml": self.example_xml,
            "description": self.description,
            "verification_status": self.verification_status,
            "confidence": self.confidence,
            "source_sheet": self.source_sheet,
            "source_row": self.source_row,
            "raw_element": self.raw_element,
        }


@dataclass(frozen=True)
class NormalizedGuide:
    version: int
    source_name: str
    rules: tuple[GuideRule, ...]
    issues: tuple[GuideIssue, ...]

    def rules_for(self, profile: str) -> tuple[GuideRule, ...]:
        return tuple(rule for rule in self.rules if rule.profile == profile)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "source_name": self.source_name,
            "rules": [rule.to_dict() for rule in self.rules],
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _parse_components(value: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    components: list[str] = []
    variants: list[str] = []
    for line in _text(value).replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        xml_tags = _XML_TAG.findall(line)
        if xml_tags:
            components.extend(xml_tags)
            continue
        variant = _VARIANT.search(line)
        if variant:
            variants.append(variant.group(1).strip())
            line = _VARIANT.sub("", line).strip()
        if line:
            components.append(line)
    return _unique(components), _unique(variants)


def _parse_attributes(value: object) -> tuple[str, ...]:
    raw = _text(value)
    if not raw or raw in {"/", "-"}:
        return ()
    return _unique(_ATTRIBUTE.findall(raw))


def _header_map(values: tuple[object, ...]) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, value in enumerate(values):
        normalized = _fold(value)
        field = _HEADER_ALIASES.get(normalized)
        if field:
            result[field] = index
    return result


def _row_value(values: tuple[object, ...], columns: dict[str, int], field: str) -> object:
    index = columns[field]
    return values[index] if index < len(values) else None


def _rule_issues(
    *,
    profile: str,
    sheet: str,
    row: int,
    description: str,
    example_xml: str,
    variants: tuple[str, ...],
) -> list[GuideIssue]:
    issues: list[GuideIssue] = []
    if not description:
        issues.append(GuideIssue(
            "MISSING_DESCRIPTION", "warning",
            "La description metier est absente dans le classeur.",
            profile, sheet, row, "description",
        ))
    if not example_xml:
        issues.append(GuideIssue(
            "MISSING_EXAMPLE", "warning",
            "L'exemple XML est absent dans le classeur.",
            profile, sheet, row, "example_xml",
        ))
    if variants:
        issues.append(GuideIssue(
            "TAG_VARIANT_NEEDS_REVIEW", "warning",
            f"La balise comporte une variante metier : {', '.join(variants)}.",
            profile, sheet, row, "element",
        ))
    return issues


def _duplicate_issues(rules: list[GuideRule]) -> list[GuideIssue]:
    groups: defaultdict[tuple[str, str], list[GuideRule]] = defaultdict(list)
    for rule in rules:
        if not rule.variants:
            groups[(rule.profile, rule.element)].append(rule)
    issues: list[GuideIssue] = []
    for (profile, element), group in groups.items():
        descriptions = {_fold(rule.description) for rule in group}
        if len(group) < 2 or len(descriptions) < 2:
            continue
        rows = ", ".join(str(rule.source_row) for rule in group)
        issues.append(GuideIssue(
            "CONFLICTING_DUPLICATE_DEFINITION", "warning",
            f"Definitions contradictoires de {element} aux lignes {rows}; aucune correction automatique.",
            profile, group[0].source_sheet, group[0].source_row, "element",
        ))
    return issues


def _load_workbook(path: Path):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - depend de l'installation
        raise AppError(
            "S1000D_GUIDE_XLSX_UNSUPPORTED",
            "Lecture XLSX indisponible : installe openpyxl.",
            503,
        ) from exc
    try:
        return load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise AppError(
            "S1000D_GUIDE_INVALID",
            f"Guide S1000D illisible : {path.name}.",
            422,
        ) from exc


def load_guide(path: str | Path = DEFAULT_GUIDE_PATH) -> NormalizedGuide:
    """Charge le guide Excel et renvoie une representation normalisee."""
    source = Path(path)
    if not source.exists():
        raise AppError("S1000D_GUIDE_NOT_FOUND", f"Guide S1000D introuvable : {source.name}.", 404)
    if source.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise AppError("S1000D_GUIDE_FORMAT", "Le guide S1000D doit etre un fichier XLSX.", 422)

    workbook = _load_workbook(source)
    rules: list[GuideRule] = []
    issues: list[GuideIssue] = []
    try:
        for worksheet in workbook.worksheets:
            profile = _SHEET_PROFILES.get(worksheet.title)
            if profile is None:
                issues.append(GuideIssue(
                    "UNSUPPORTED_SHEET", "warning",
                    f"Onglet ignore car aucun profil S1000D n'est defini : {worksheet.title}.",
                    "unknown", worksheet.title, 1,
                ))
                continue

            rows = worksheet.iter_rows(values_only=True)
            header = next(rows, None)
            columns = _header_map(header or ())
            missing_columns = sorted(_REQUIRED_COLUMNS - set(columns))
            if missing_columns:
                issues.append(GuideIssue(
                    "MISSING_COLUMN", "error",
                    f"Colonnes absentes dans l'onglet {worksheet.title} : {', '.join(missing_columns)}.",
                    profile, worksheet.title, 1,
                ))
                continue

            issues.append(GuideIssue(
                "STRUCTURE_NOT_SPECIFIED", "warning",
                "Le classeur ne specifie pas les parents et enfants autorises; verification schema requise.",
                profile, worksheet.title, 1, "parents_children",
            ))

            for source_row, values in enumerate(rows, start=2):
                if not any(_text(value) for value in values):
                    continue
                raw_element = _text(_row_value(values, columns, "element"))
                if not raw_element:
                    issues.append(GuideIssue(
                        "MISSING_ELEMENT", "error",
                        "Ligne ignoree car le nom de balise est absent.",
                        profile, worksheet.title, source_row, "element",
                    ))
                    continue

                components, variants = _parse_components(raw_element)
                if not components:
                    issues.append(GuideIssue(
                        "INVALID_ELEMENT", "error",
                        f"Nom de balise non interpretable : {raw_element}.",
                        profile, worksheet.title, source_row, "element",
                    ))
                    continue

                description = _text(_row_value(values, columns, "description"))
                example_text = _text(_row_value(values, columns, "example"))
                example_xml = _text(_row_value(values, columns, "example_xml"))
                local_issues = _rule_issues(
                    profile=profile,
                    sheet=worksheet.title,
                    row=source_row,
                    description=description,
                    example_xml=example_xml,
                    variants=variants,
                )
                issues.extend(local_issues)
                rules.append(GuideRule(
                    profile=profile,
                    element=components[0],
                    components=components,
                    variants=variants,
                    business_role=_ROLE_BY_ELEMENT.get(components[0]),
                    allowed_parents=None,
                    allowed_children=None,
                    required_attributes=_parse_attributes(
                        _row_value(values, columns, "required_attributes")
                    ),
                    optional_attributes=_parse_attributes(
                        _row_value(values, columns, "optional_attributes")
                    ),
                    example_text=example_text or None,
                    example_xml=example_xml or None,
                    description=description or None,
                    verification_status="needs_review" if local_issues else "unverified",
                    confidence="low" if local_issues else "medium",
                    source_sheet=worksheet.title,
                    source_row=source_row,
                    raw_element=raw_element,
                ))
    finally:
        workbook.close()

    issues.extend(_duplicate_issues(rules))
    if not rules:
        raise AppError("S1000D_GUIDE_EMPTY", "Le guide S1000D ne contient aucune regle exploitable.", 422)
    return NormalizedGuide(GUIDE_VERSION, source.name, tuple(rules), tuple(issues))


__all__ = [
    "DEFAULT_GUIDE_PATH",
    "GUIDE_VERSION",
    "GuideIssue",
    "GuideRule",
    "NormalizedGuide",
    "load_guide",
]