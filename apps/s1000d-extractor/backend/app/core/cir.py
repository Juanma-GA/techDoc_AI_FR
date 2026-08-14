"""CIR (Common Information Repository) : contenus partages entre Data Modules.

Warnings, cautions, notes, outillages et consommables sont mutualises dans un
CIR : les DM ne les recopient pas, ils y font reference. Ce module charge le CIR
(XML) et resout les references trouvees dans un DM.

References reconnues dans le texte d'un noeud IR :

    {{CIR:WARN-001}}   [CIR:WARN-001]   <cirRef refId="WARN-001"/>

Une reference introuvable n'est PAS effacee : elle est conservee telle quelle et
remontee dans `unresolved` (jamais de perte silencieuse de contenu).
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

from app.core import xml_safe
from app.core.errors import AppError

_REF_RE = re.compile(
    r"\{\{\s*CIR\s*:\s*([A-Za-z0-9_.\-]+)\s*\}\}"
    r"|\[\s*CIR\s*:\s*([A-Za-z0-9_.\-]+)\s*\]"
    r"|<cirRef[^>]*refId=[\"']([A-Za-z0-9_.\-]+)[\"'][^>]*/?>",
)

_ID_ATTRS = ("id", "ident", "identNumber", "refId", "cirId")
_TYPE_HINTS = {
    "warning": "warning", "caution": "caution", "note": "note",
    "toolref": "tool", "supplyref": "supply", "partref": "part",
}


def _localname(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _entry_id(el: etree._Element) -> str:
    for attr in _ID_ATTRS:
        value = el.get(attr)
        if value:
            return value
    return ""


def _entry_text(el: etree._Element) -> str:
    return " ".join(t.strip() for t in el.itertext() if t and t.strip())


def load_cir(file_path: str | Path) -> dict[str, dict]:
    """Charge un CIR XML -> `{id: {id, type, text}}`.

    Tolerant : tout element portant un identifiant (`id`, `ident`,
    `identNumber`, `refId`, `cirId`) devient une entree, quel que soit le
    vocabulaire exact du fichier client.
    """
    path = Path(file_path)
    if not path.exists():
        raise AppError("CIR_NOT_FOUND", f"CIR introuvable : {path.name}", 404)
    try:
        root = xml_safe.fromstring(path.read_bytes())
    except etree.XMLSyntaxError as exc:
        raise AppError("CIR_INVALID", f"CIR mal forme : {exc}", 422) from exc

    entries: dict[str, dict] = {}
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        ident = _entry_id(el)
        if not ident or ident in entries:
            continue
        local = _localname(el.tag).lower()
        entries[ident] = {
            "id": ident,
            "type": _TYPE_HINTS.get(local, local),
            "text": _entry_text(el),
        }
    if not entries:
        raise AppError("CIR_EMPTY", "Aucune entree identifiee dans le CIR.", 422)
    return entries


def _resolve_text(
    text: str, cir: dict[str, dict], used: list[str], unresolved: list[str]
) -> str:
    def repl(match: re.Match[str]) -> str:
        ident = next((g for g in match.groups() if g), "")
        entry = cir.get(ident)
        if entry is None:
            unresolved.append(ident)
            return match.group(0)
        used.append(ident)
        return entry.get("text") or match.group(0)

    return _REF_RE.sub(repl, text or "")


def _resolve_tree(node: dict, cir: dict[str, dict], used: list[str], unresolved: list[str]) -> dict:
    return {
        **node,
        "text": _resolve_text(node.get("text") or "", cir, used, unresolved),
        "children": [_resolve_tree(c, cir, used, unresolved) for c in node.get("children") or []],
    }


def resolve_cir_references(dm: dict, cir: dict[str, dict]) -> dict:
    """Remplace les references CIR d'un DM par le contenu du repository.

    Traite le texte de l'arbre IR (`tree`), des rubriques de template
    (`sections[].content`) et du titre. Renvoie un NOUVEAU DM enrichi de
    `cir_used` (ids resolus) et `cir_unresolved` (ids introuvables).
    """
    if not cir:
        return dict(dm)
    unresolved: list[str] = []
    used: list[str] = []
    out = dict(dm)
    out["title"] = _resolve_text(dm.get("title") or "", cir, used, unresolved)
    if dm.get("tree"):
        out["tree"] = _resolve_tree(dm["tree"], cir, used, unresolved)
    if dm.get("sections"):
        out["sections"] = [
            {**s, "content": _resolve_text(str(s.get("content") or ""), cir, used, unresolved)}
            if isinstance(s, dict) else s
            for s in dm["sections"]
        ]
    out["cir_used"] = sorted(set(used))
    out["cir_unresolved"] = sorted(set(unresolved))
    return out
