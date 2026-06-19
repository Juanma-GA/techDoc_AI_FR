"""Schemas S1000D par Issue : validation XSD + vocabulaire d'elements.

Les jeux de schemas officiels (volumineux) ne sont pas redistribues dans le
repo. On les charge depuis `app/s1000d_schemas/issue-<x>/` si presents (drop
manuel ou `scripts/fetch_s1000d_schemas.py`). Absents -> la validation XSD est
signalee "non installee" (degradation gracieuse), mais le vocabulaire intern
(table ci-dessous) reste disponible pour la resolution.

Issues supportees : 4.2 et 5.0. Les noms d'elements du squelette sont stables
entre les deux (heritage du redesign Issue 4.0).
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

SUPPORTED_ISSUES = ("4.2", "5.0")
_SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "s1000d_schemas"

# Vocabulaire d'elements legaux par contexte (sous-ensemble structurel v1).
# Sert de garde-fou meme sans XSD officiel installe.
_VOCAB: dict[str, set[str]] = {
    "descriptive": {
        "levelledPara", "title", "para", "randomList", "sequentialList",
        "listItem", "warning", "caution", "note", "warningAndCautionPara",
        "notePara", "figure", "graphic", "table", "tgroup", "tbody", "row", "entry",
    },
    "procedural": {
        "proceduralStep", "para", "warning", "caution", "note",
        "warningAndCautionPara", "notePara", "figure", "graphic",
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


def _find_dm_xsd(issue: str) -> Path | None:
    d = _issue_dir(issue)
    if not d.is_dir():
        return None
    # Heuristique : on prend le schema 'descript' ou le premier *.xsd.
    for pat in ("descript*.xsd", "proced*.xsd", "*.xsd"):
        hits = sorted(d.glob(pat))
        if hits:
            return hits[0]
    return None


def validate_xsd(xml: str, issue: str) -> list[dict]:
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
    xsd_path = _find_dm_xsd(issue)
    if xsd_path is None:
        return [_v("info", "XSD", f"Aucun .xsd trouve pour l'Issue {issue}.", "/")]
    try:
        schema = etree.XMLSchema(etree.parse(str(xsd_path)))
        doc = etree.fromstring(xml.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return [_v("error", "XSD", f"XML mal forme : {exc}", "/")]
    except Exception as exc:
        return [_v("info", "XSD", f"Chargement XSD impossible : {exc}", "/")]
    if schema.validate(doc):
        return []
    return [
        _v("error", "XSD", e.message, e.path or "/")
        for e in schema.error_log  # type: ignore[union-attr]
    ]


def _v(severity: str, rule: str, message: str, path: str) -> dict:
    return {"severity": severity, "rule": rule, "message": message, "path": path}
