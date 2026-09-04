"""Validation du squelette produit : well-formedness + XSD + BREX.

Ordre metier : un instance peut etre XSD-valide mais BREX-invalide, donc on
lance les deux. Le squelette etant volontairement incomplet (placeholders
DMC/ICN), la validation XSD officielle remontera des manques *attendus* - ils
servent de check-list de completion pour l'humain, pas d'echec bloquant.

Regle de robustesse : la validation NE LEVE JAMAIS. Un validateur qui plante
(XSD exotique, XPath BREX invalide) doit produire une violation lisible, pas une
"Unexpected server error" cote UI. Aucun appel IA n'a lieu ici : la validation
est purement deterministe.
"""

from __future__ import annotations

import logging

from lxml import etree

from app.core import brex as brex_mod
from app.core import s1000d_schema, xml_safe

log = logging.getLogger("s1000d_extractor.validator")


def _v(severity: str, rule: str, message: str, path: str = "/") -> dict:
    return {"severity": severity, "rule": rule, "message": message, "path": path}


def validate_document(
    xml: str,
    *,
    issue: str,
    brex_xml: str | None = None,
    brex_rules: dict | None = None,
    dm: dict | None = None,
) -> list[dict]:
    violations: list[dict] = []

    # 1. Well-formedness (toujours).
    try:
        xml_safe.fromstring(xml)
    except etree.XMLSyntaxError as exc:
        return [_v("error", "WELLFORMED", f"XML mal forme : {exc}")]

    # 2. XSD officiel (si installe pour l'Issue).
    try:
        violations.extend(s1000d_schema.validate_xsd(xml, issue))
    except Exception as exc:
        log.warning("XSD validation failed: %s", exc)
        # `warning`, pas `info` : "non validee" ne doit pas se lire comme "validee
        # avec une remarque benigne".
        violations.append(_v("warning", "XSD", f"Validation XSD NON EXECUTEE : {exc}"))

    # 3. BREX projet (si fourni).
    if brex_xml:
        try:
            rules = brex_mod.parse_brex(brex_xml)
            violations.extend(brex_mod.validate_brex(xml, rules))
        except Exception as exc:
            log.warning("BREX validation failed: %s", exc)
            violations.append(_v("warning", "BREX", f"Validation BREX NON EXECUTEE : {exc}"))

    # 4. Regles client (BREX JSON) sur le DM lui-meme, si fournies.
    if brex_rules and dm is not None:
        from app.core.brex_rules import validate_dm_against_brex

        try:
            violations.extend(validate_dm_against_brex(dm, brex_rules))
        except Exception as exc:
            log.warning("client BREX rules failed: %s", exc)
            violations.append(
                _v("warning", "BREX_RULES", f"Regles client NON APPLIQUEES : {exc}")
            )

    return violations
