"""Schemas S1000D par Issue : validation XSD + vocabulaire d'elements.

Les jeux de schemas officiels (volumineux) sont charges depuis
`app/s1000d_schemas/issue-<x>/` lorsqu'ils sont presents. Absents -> la validation XSD est
signalee "non installee" (degradation gracieuse), mais le vocabulaire intern
(table ci-dessous) reste disponible pour la resolution.

Issues reconnues par le validateur : 4.1, 4.2 et 5.0. Issue 5.0 reste
disponible pour verifier les anciens fichiers, mais sans XSD local elle est
non verifiable. Seules 4.1 et 4.2 sont selectionnables pour la generation.
"""

from __future__ import annotations

import re
from _thread import LockType
from pathlib import Path
from threading import Lock

from lxml import etree

from app.core import xml_safe

SUPPORTED_ISSUES = ("4.1", "4.2", "5.0")
SELECTABLE_ISSUES = ("4.1", "4.2")
_SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "s1000d_schemas"
_SCHEMA_CACHE: dict[Path, tuple[etree.XMLSchema, LockType]] = {}
_SCHEMA_CACHE_LOCK = Lock()
SCHEMA_STEMS = {
    "descriptive": "descript",
    "description": "descript",
    "descript": "descript",
    "procedural": "proced",
    "procedure": "proced",
    "proced": "proced",
    "ipd": "ipd",
}

# Vocabulaire d'elements legaux par contexte (sous-ensemble structurel v1).
# Sert de garde-fou meme sans XSD officiel installe.
_VOCAB: dict[str, set[str]] = {
    "descriptive": {
        "levelledPara", "title", "para", "randomList", "sequentialList",
        "listItem", "warning", "caution", "note", "warningAndCautionPara",
        "notePara", "attentionSequentialList", "attentionSequentialListItem",
        "attentionListItemPara", "figure", "graphic", "table", "tgroup", "tbody", "row", "entry",
    },
    "procedural": {
        "proceduralStep", "para", "warning", "caution", "note",
        "warningAndCautionPara", "notePara", "attentionSequentialList",
        "attentionSequentialListItem", "attentionListItemPara", "figure", "graphic",
        "table", "tgroup", "tbody", "row", "entry", "title",
    },
}


def allowed_elements(context: str) -> set[str]:
    return _VOCAB.get(context, _VOCAB["descriptive"])


def _issue_dir(issue: str) -> Path:
    return _SCHEMA_ROOT / f"issue-{issue}"


def is_installed(issue: str) -> bool:
    d = _issue_dir(issue)
    return d.is_dir() and any(d.glob("*.xsd"))


def _find_dm_xsd(issue: str, dm_type: str | None = None) -> Path | None:
    d = _issue_dir(issue)
    if not d.is_dir() or not dm_type:
        return None
    normalized_type = dm_type.lower().removesuffix(".xsd")
    schema_stem = SCHEMA_STEMS.get(normalized_type)
    if schema_stem is None or not re.fullmatch(r"[a-z][a-z0-9_-]*", schema_stem):
        return None
    schema_path = d / f"{schema_stem}.xsd"
    return schema_path if schema_path.is_file() else None


def _compiled_schema(path: Path) -> tuple[etree.XMLSchema, LockType]:
    resolved_path = path.resolve()
    with _SCHEMA_CACHE_LOCK:
        cached = _SCHEMA_CACHE.get(resolved_path)
        if cached is None:
            cached = (etree.XMLSchema(xml_safe.parse(str(resolved_path))), Lock())
            _SCHEMA_CACHE[resolved_path] = cached
        return cached


def validate_xsd(
    xml: str | bytes,
    issue: str,
    *,
    dm_type: str | None = None,
    allow_internal_dtd: bool = False,
) -> list[dict]:
    """Valide le XML contre le XSD officiel de l'Issue si installe.

    Renvoie une liste de violations `{severity, rule, message, path}`. Une
    entree 'info' signale l'absence de schema (au lieu d'echouer).
    """
    if issue not in SUPPORTED_ISSUES:
        return [_v("error", "XSD", f"Issue non supportee : {issue}", "/")]
    if not is_installed(issue):
        return [_v(
            "info", "XSD",
            f"Schemas officiels Issue {issue} non installes "
            f"(app/s1000d_schemas/issue-{issue}/). Validation XSD ignoree.",
            "/",
        )]
    try:
        doc = xml_safe.fromstring(xml, allow_internal_dtd=allow_internal_dtd)
        selected_type = dm_type
        if selected_type is None:
            if doc.find("./content/procedure") is not None:
                selected_type = "procedural"
            elif doc.find("./content/ipd") is not None:
                selected_type = "ipd"
            else:
                selected_type = "descriptive"
        xsd_path = _find_dm_xsd(issue, selected_type)
        if xsd_path is None:
            return [_v(
                "info", "XSD",
                f"Aucun schema DM correspondant au type '{selected_type}' pour l'Issue {issue}.",
                "/",
            )]
        schema, lock = _compiled_schema(xsd_path)
    except etree.XMLSyntaxError as exc:
        return [_v("error", "XSD", f"XML mal forme : {exc}", "/")]
    except Exception as exc:
        return [_v("info", "XSD", f"Chargement XSD impossible : {exc}", "/")]
    with lock:
        if schema.validate(doc):
            return []
        return [
            {
                **_v("error", "XSD", e.message, e.path or "/"),
                "line": e.line or None,
                "column": e.column or None,
            }
            for e in schema.error_log
        ]


def _v(severity: str, rule: str, message: str, path: str) -> dict:
    return {"severity": severity, "rule": rule, "message": message, "path": path}
