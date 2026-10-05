"""Schemas S1000D par Issue : validation XSD + vocabulaire d'elements.

Les jeux de schemas officiels (volumineux) sont charges depuis
`app/s1000d_schemas/issue-<x>/` lorsqu'ils sont presents. Absents -> la validation XSD est
signalee "non installee" (degradation gracieuse), mais le vocabulaire intern
(table ci-dessous) reste disponible pour la resolution.

Issues supportees : 4.1, 4.2 et 5.0. Les noms d'elements du squelette sont stables
entre les deux (heritage du redesign Issue 4.0).
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

from app.core import xml_safe

SUPPORTED_ISSUES = ("4.1", "4.2", "5.0")
_SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "s1000d_schemas"

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
    if not d.is_dir():
        return None
    schema_stem = {
        "descriptive": "descript",
        "procedural": "proced",
    }.get((dm_type or "").lower(), (dm_type or "").lower().removesuffix(".xsd"))
    if schema_stem and re.fullmatch(r"[a-z][a-z0-9_-]*", schema_stem):
        explicit = d / f"{schema_stem}.xsd"
        if explicit.is_file():
            return explicit
    preferred = "proced*.xsd" if dm_type == "procedural" else "descript*.xsd"
    # Le type du DM choisit le schema correspondant ; le premier schema reste
    # un repli pour les anciennes installations mono-XSD.
    for pat in (preferred, "descript*.xsd", "proced*.xsd", "*.xsd"):
        hits = sorted(d.glob(pat))
        if hits:
            return hits[0]
    return None


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
    xsd_path = _find_dm_xsd(issue, dm_type)
    if xsd_path is None:
        return [_v("info", "XSD", f"Aucun .xsd trouve pour l'Issue {issue}.", "/")]
    try:
        doc = xml_safe.fromstring(xml, allow_internal_dtd=allow_internal_dtd)
        selected_type = dm_type
        if selected_type is None:
            selected_type = "procedural" if doc.find("./content/procedure") is not None else "descriptive"
        xsd_path = _find_dm_xsd(issue, selected_type) or xsd_path
        schema = etree.XMLSchema(xml_safe.parse(str(xsd_path)))
    except etree.XMLSyntaxError as exc:
        return [_v("error", "XSD", f"XML mal forme : {exc}", "/")]
    except Exception as exc:
        return [_v("info", "XSD", f"Chargement XSD impossible : {exc}", "/")]
    if schema.validate(doc):
        return []
    return [
        {
            **_v("error", "XSD", e.message, e.path or "/"),
            "line": e.line or None,
            "column": e.column or None,
        }
        for e in schema.error_log  # type: ignore[union-attr]
    ]


def _v(severity: str, rule: str, message: str, path: str) -> dict:
    return {"severity": severity, "rule": rule, "message": message, "path": path}
