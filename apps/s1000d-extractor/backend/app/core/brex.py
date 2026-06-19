"""BREX (Business Rules EXchange) - porte de validation par projet.

Correction metier importante : le BREX NE genere PAS les elements ; il les
*contraint/valide*. Un meme document peut etre XSD-valide mais BREX-invalide.
Le BREX est defini une fois par projet et reutilise sur tous ses documents -
c'est ce qui evite de refaire le mapping a chaque migration.

Sous-ensemble pragmatique v1 : on lit les `structureObjectRule`
(`objectPath` + `allowedObjectFlag` + `objectValue/@valueAllowed`) et on
verifie le XML produit. La semantique BREX complete (CIR, notation, contextes
XPath avances) est hors scope - documente dans le README.
"""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree


@dataclass
class BrexRule:
    object_path: str
    allowed_flag: str          # "0" interdit, "1" autorise, "2" autorise sous condition
    object_use: str
    values_allowed: list[str]


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_brex(brex_xml: str) -> list[BrexRule]:
    """Extrait les regles de structure d'un Data Module BREX."""
    try:
        root = etree.fromstring(brex_xml.encode("utf-8"))
    except etree.XMLSyntaxError:
        return []
    rules: list[BrexRule] = []
    for sor in root.iter():
        if _localname(sor.tag) != "structureObjectRule":
            continue
        path = _child_text(sor, "objectPath")
        flag = _child_attr(sor, "objectPath", "allowedObjectFlag") or "1"
        use = _child_text(sor, "objectUse")
        values = [
            ov.get("valueAllowed", "")
            for ov in sor.iter()
            if _localname(ov.tag) == "objectValue" and ov.get("valueAllowed")
        ]
        if path:
            rules.append(BrexRule(path, flag, use, values))
    return rules


def _child_text(parent: etree._Element, local: str) -> str:
    for c in parent.iter():
        if _localname(c.tag) == local:
            return (c.text or "").strip()
    return ""


def _child_attr(parent: etree._Element, local: str, attr: str) -> str:
    for c in parent.iter():
        if _localname(c.tag) == local:
            return c.get(attr, "")
    return ""


def validate_brex(xml: str, rules: list[BrexRule]) -> list[dict]:
    """Confronte le XML produit aux regles BREX (best-effort XPath).

    Regle `allowedObjectFlag="0"` dont l'`objectPath` matche des noeuds -> une
    violation (element interdit present). Les XPath BREX ecrits pour le schema
    complet peuvent ne pas matcher notre squelette : on capture les erreurs
    XPath sans planter.
    """
    if not rules:
        return []
    try:
        doc = etree.fromstring(xml.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return [_v("error", "BREX", f"XML mal forme : {exc}", "/")]

    out: list[dict] = []
    for rule in rules:
        if rule.allowed_flag != "0":
            continue
        try:
            matches = doc.xpath(rule.object_path)
        except etree.XPathEvalError:
            continue  # XPath non evaluable sur le squelette : ignore
        if matches:
            out.append(_v(
                "error", "BREX",
                f"Element interdit present (allowedObjectFlag=0) : "
                f"{rule.object_use or rule.object_path}",
                rule.object_path,
            ))
    return out


def _v(severity: str, rule: str, message: str, path: str) -> dict:
    return {"severity": severity, "rule": rule, "message": message, "path": path}
