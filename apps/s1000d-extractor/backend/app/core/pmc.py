"""Generation de la PMC (Publication Module Code) a partir d'une DMRL.

La PMC est la table des matieres S1000D : un `pm` dont le `content` est un arbre
de `pmEntry` refletant l'arborescence (`Arbo`) de la DMRL, chaque feuille
portant un `dmRef` vers le Data Module correspondant.

Separe de `dmrl.py` (qui charge/parse la DMRL) pour tenir la limite de taille
des fichiers et isoler la construction XML.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lxml import etree

if TYPE_CHECKING:  # pragma: no cover - import de typage seulement
    from app.core.dmrl import DmrlEntry

# DMC standard : DMC-<mic>-<sdc>-<sc>-<ssc+sssc>-<ac>-<dc+dcv>-<ic+icv>-<ilc>
_DMC_RE = re.compile(
    r"^(?:DMC-)?"
    r"(?P<mic>[A-Z0-9]+)-"
    r"(?P<sdc>[A-Z0-9]{1,2})-"
    r"(?P<sc>[A-Z0-9]{2,3})-"
    r"(?P<ssc>[A-Z0-9])(?P<sssc>[A-Z0-9])-"
    r"(?P<ac>[A-Z0-9]{2,4})-"
    r"(?P<dc>[0-9]{2})(?P<dcv>[A-Z])-"
    r"(?P<ic>[0-9]{3})(?P<icv>[A-Z])-"
    r"(?P<ilc>[A-Z])$",
    re.IGNORECASE,
)


def parse_dmc(dmc: str) -> dict[str, str] | None:
    """Eclate un DMC en ses composants S1000D. `None` si le code est non standard."""
    m = _DMC_RE.match((dmc or "").strip())
    if not m:
        return None
    g = m.groupdict()
    return {
        "modelIdentCode": g["mic"].upper(),
        "systemDiffCode": g["sdc"].upper(),
        "systemCode": g["sc"].upper(),
        "subSystemCode": g["ssc"].upper(),
        "subSubSystemCode": g["sssc"].upper(),
        "assyCode": g["ac"].upper(),
        "disassyCode": g["dc"],
        "disassyCodeVariant": g["dcv"].upper(),
        "infoCode": g["ic"],
        "infoCodeVariant": g["icv"].upper(),
        "itemLocationCode": g["ilc"].upper(),
    }


def _arbo_parts(arbo: str) -> list[str]:
    return [p for p in re.split(r"[.\-/]", (arbo or "").strip()) if p]


def _emit_dm_ref(parent: etree._Element, entry: DmrlEntry) -> None:
    if not entry.dmc:
        return
    ref = etree.SubElement(parent, "dmRef")
    ident = etree.SubElement(ref, "dmRefIdent")
    parsed = parse_dmc(entry.dmc)
    if parsed:
        etree.SubElement(ident, "dmCode", **parsed)
    else:
        ident.append(etree.Comment(f" DMC non standard (a corriger) : {entry.dmc} "))
        etree.SubElement(ident, "dmCode", dmCodeValue=entry.dmc)
    items = etree.SubElement(ref, "dmRefAddressItems")
    title = etree.SubElement(items, "dmTitle")
    etree.SubElement(title, "techName").text = entry.tech_name or entry.title
    if entry.info_name:
        etree.SubElement(title, "infoName").text = entry.info_name


def _emit_entry(parent: etree._Element, node: dict) -> None:
    entries: list[DmrlEntry] = node["entries"]
    el = etree.SubElement(parent, "pmEntry")
    label = entries[0].title if entries else node["key"]
    etree.SubElement(el, "pmEntryTitle").text = label
    for entry in entries:
        _emit_dm_ref(el, entry)
    for child in node["children"]:
        _emit_entry(el, child)


def _build_tree(entries: list[DmrlEntry]) -> list[dict]:
    """Construit l'arbre depuis des niveaux numeriques ou des chemins `Arbo`."""
    levels: list[int | None] = []
    numeric_levels = True
    for entry in entries:
        value = str(entry.arbo or "").strip()
        if not value:
            levels.append(None)
        elif re.fullmatch(r"\d+", value):
            levels.append(int(value))
        else:
            numeric_levels = False
            break

    if numeric_levels and any(level is not None for level in levels):
        roots: list[dict] = []
        stack: list[tuple[int, dict]] = []
        for entry, level in zip(entries, levels):
            node = {"key": entry.title or entry.dmc, "entries": [entry], "children": []}
            if level is None:
                roots.append(node)
                stack.clear()
                continue
            while stack and stack[-1][0] >= level:
                stack.pop()
            if level == 1 or not stack:
                roots.append(node)
            else:
                stack[-1][1]["children"].append(node)
            stack.append((level, node))
        return roots

    roots: list[dict] = []
    index: dict[str, dict] = {}
    for entry in entries:
        parts = _arbo_parts(entry.arbo)
        if not parts:
            roots.append({"key": entry.title, "entries": [entry], "children": []})
            continue
        path = ""
        parent_children = roots
        for i, part in enumerate(parts):
            path = f"{path}.{part}" if path else part
            node = index.get(path)
            if node is None:
                node = {"key": path, "entries": [], "children": []}
                index[path] = node
                parent_children.append(node)
            if i == len(parts) - 1:
                node["entries"].append(entry)
            parent_children = node["children"]
    return roots


def generate_pmc(entries: list[DmrlEntry], *, pm_title: str = "Publication") -> str:
    """Construit la PMC (XML S1000D `pm`) depuis les entrees de la DMRL."""
    pm = etree.Element("pm")
    pm.addprevious(etree.Comment(
        " PMC generee depuis la DMRL. pmCode / issueInfo / language a completer. "
    ))
    ident = etree.SubElement(pm, "identAndStatusSection")
    address = etree.SubElement(ident, "pmAddress")
    address.append(etree.Comment(" TODO: pmCode (modelIdentCode, pmIssuer, pmNumber, pmVolume) "))
    etree.SubElement(address, "pmCode")
    title_el = etree.SubElement(address, "pmTitle")
    title_el.text = pm_title
    etree.SubElement(ident, "pmStatus")

    content = etree.SubElement(pm, "content")
    for node in _build_tree(entries):
        _emit_entry(content, node)

    return etree.tostring(
        pm.getroottree(), pretty_print=True, xml_declaration=True, encoding="UTF-8"
    ).decode("utf-8")
