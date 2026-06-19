"""Validation du squelette produit : well-formedness + XSD + BREX.

Ordre metier : un instance peut etre XSD-valide mais BREX-invalide, donc on
lance les deux. Le squelette etant volontairement incomplet (placeholders
DMC/ICN), la validation XSD officielle remontera des manques *attendus* - ils
servent de check-list de completion pour l'humain, pas d'echec bloquant.
"""

from __future__ import annotations

from lxml import etree

from app.core import brex as brex_mod
from app.core import s1000d_schema


def validate_document(
    xml: str, *, issue: str, brex_xml: str | None = None
) -> list[dict]:
    violations: list[dict] = []

    # 1. Well-formedness (toujours).
    try:
        etree.fromstring(xml.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return [{"severity": "error", "rule": "WELLFORMED",
                 "message": f"XML mal forme : {exc}", "path": "/"}]

    # 2. XSD officiel (si installe pour l'Issue).
    violations.extend(s1000d_schema.validate_xsd(xml, issue))

    # 3. BREX projet (si fourni).
    if brex_xml:
        rules = brex_mod.parse_brex(brex_xml)
        violations.extend(brex_mod.validate_brex(xml, rules))

    return violations
