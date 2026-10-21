"""Parsing XML durci pour les fichiers fournis par l'utilisateur.

Tout XML venant d'un upload (BREX, CIR) est hostile par defaut : le parseur
`lxml` resout les entites externes, ce qui ouvre une XXE (lecture de fichiers
locaux, SSRF) et une bombe d'entites. Ce module centralise le seul parseur
autorise pour ces entrees.
"""

from __future__ import annotations

from lxml import etree


def safe_parser() -> etree.XMLParser:
    """Parseur sans entites externes, sans reseau, sans DTD."""
    return etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False,
        dtd_validation=False, huge_tree=False,
    )


def _reject_dtd(tree: etree._ElementTree, *, allow_internal_dtd: bool = False) -> None:
    """Always refuse external DTDs; internal subsets require explicit opt-in."""
    info = tree.docinfo
    has_external_subset = (
        info.externalDTD is not None or info.system_url is not None or info.public_id is not None
    )
    if has_external_subset or (info.internalDTD is not None and not allow_internal_dtd):
        reason = "DTD externe interdite." if has_external_subset else "DTD interdite."
        raise etree.XMLSyntaxError(
            f"{reason} Retire le <!DOCTYPE> externe (risque XXE / bombe d'entites).",
            0, 0, 0,
        )


def fromstring(data: bytes | str, *, allow_internal_dtd: bool = False) -> etree._Element:
    """`etree.fromstring` durci. Leve `etree.XMLSyntaxError` comme l'original."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    root = etree.fromstring(raw, safe_parser())
    _reject_dtd(root.getroottree(), allow_internal_dtd=allow_internal_dtd)
    return root


def parse(source: str, *, allow_internal_dtd: bool = False) -> etree._ElementTree:
    """`etree.parse` durci (schemas XSD deposes localement)."""
    tree = etree.parse(source, safe_parser())
    _reject_dtd(tree, allow_internal_dtd=allow_internal_dtd)
    return tree
