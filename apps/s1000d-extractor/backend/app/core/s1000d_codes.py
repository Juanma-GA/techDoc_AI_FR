"""Registre local des codes S1000D normalises pour le projet."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from app.core.errors import AppError

DEFAULT_CODES_PATH = Path(__file__).resolve().parents[1] / "s1000d_codes.json"


@dataclass(frozen=True)
class CodeValue:
    code: str
    label: str
    status: str
    style: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, str]:
        data = {"code": self.code, "label": self.label, "status": self.status}
        if self.style:
            data["style"] = self.style
        if self.notes:
            data["notes"] = self.notes
        return data


@dataclass(frozen=True)
class CodeSet:
    name: str
    source_page: int | None
    values: tuple[CodeValue, ...]
    project_ranges: tuple[dict[str, Any], ...] = ()

    def value(self, code: str) -> CodeValue | None:
        normalized = (code or "").strip()
        explicit = next((value for value in self.values if value.code == normalized), None)
        if explicit:
            return explicit
        for project_range in self.project_ranges:
            prefix = str(project_range.get("prefix") or "")
            suffix = normalized[len(prefix):] if normalized.startswith(prefix) else ""
            if not suffix.isdigit():
                continue
            number = int(suffix)
            if int(project_range.get("start", 0)) <= number <= int(project_range.get("end", -1)):
                return CodeValue(
                    code=normalized,
                    label=str(project_range.get("label") or "Available for projects"),
                    status=str(project_range.get("status") or "project"),
                    notes=str(project_range.get("notes")) if project_range.get("notes") else None,
                )
        return None

    def expanded_values(self) -> tuple[CodeValue, ...]:
        values = list(self.values)
        for project_range in self.project_ranges:
            prefix = str(project_range.get("prefix") or "")
            label = str(project_range.get("label") or "Available for projects")
            status = str(project_range.get("status") or "project")
            for number in range(int(project_range.get("start", 0)), int(project_range.get("end", -1)) + 1):
                values.append(CodeValue(f"{prefix}{number:02d}", label, status))
        return tuple(values)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "source_page": self.source_page,
            "values": [value.to_dict() for value in self.values],
            "project_ranges": [dict(item) for item in self.project_ranges],
        }


@dataclass(frozen=True)
class NormalizedCodes:
    version: int
    standard: str
    code_sets: tuple[CodeSet, ...]
    style_to_emphasis: dict[str, str]

    def code_set(self, name: str) -> CodeSet | None:
        return next((item for item in self.code_sets if item.name == name), None)

    def code(self, set_name: str, code: str) -> CodeValue | None:
        code_set = self.code_set(set_name)
        return code_set.value(code) if code_set else None

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "standard": self.standard,
            "code_sets": [code_set.to_dict() for code_set in self.code_sets],
            "style_to_emphasis": dict(self.style_to_emphasis),
        }


def _as_code_value(data: object) -> CodeValue:
    if not isinstance(data, dict) or not data.get("code") or not data.get("label"):
        raise ValueError("code value must contain code and label")
    return CodeValue(
        code=str(data["code"]),
        label=str(data["label"]),
        status=str(data.get("status") or "unverified"),
        style=str(data["style"]) if data.get("style") else None,
        notes=str(data["notes"]) if data.get("notes") else None,
    )


def _load_codes(path: Path) -> NormalizedCodes:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("root must be an object")
        raw_sets = data.get("code_sets")
        if not isinstance(raw_sets, dict):
            raise ValueError("code_sets must be an object")
        code_sets = []
        for name, raw_set in raw_sets.items():
            if not isinstance(raw_set, dict):
                raise ValueError(f"code set {name} must be an object")
            code_sets.append(CodeSet(
                name=str(name),
                source_page=int(raw_set["source_page"]) if raw_set.get("source_page") else None,
                values=tuple(_as_code_value(item) for item in raw_set.get("values", [])),
                project_ranges=tuple(raw_set.get("project_ranges") or ()),
            ))
        style_to_emphasis = {
            str(style): str(code)
            for style, code in (data.get("style_to_emphasis") or {}).items()
        }
        return NormalizedCodes(
            version=int(data.get("version", 1)),
            standard=str(data.get("standard") or ""),
            code_sets=tuple(code_sets),
            style_to_emphasis=style_to_emphasis,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise AppError("S1000D_CODES_INVALID", f"Registre de codes illisible : {path.name}.", 422) from exc


@lru_cache(maxsize=8)
def load_codes(path: str | Path = DEFAULT_CODES_PATH) -> NormalizedCodes:
    source = Path(path)
    if not source.exists():
        raise AppError("S1000D_CODES_NOT_FOUND", f"Registre de codes introuvable : {source.name}.", 404)
    return _load_codes(source)


def codes_for(set_name: str, path: str | Path = DEFAULT_CODES_PATH) -> tuple[CodeValue, ...]:
    code_set = load_codes(path).code_set(set_name)
    return code_set.expanded_values() if code_set else ()


def get_code(set_name: str, code: str, path: str | Path = DEFAULT_CODES_PATH) -> CodeValue | None:
    return load_codes(path).code(set_name, code)


def emphasis_code_for_style(style: str, path: str | Path = DEFAULT_CODES_PATH) -> str | None:
    return load_codes(path).style_to_emphasis.get((style or "").strip().casefold())


__all__ = [
    "CodeSet",
    "CodeValue",
    "DEFAULT_CODES_PATH",
    "NormalizedCodes",
    "codes_for",
    "emphasis_code_for_style",
    "get_code",
    "load_codes",
]