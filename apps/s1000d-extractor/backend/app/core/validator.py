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

import structlog
from lxml import etree

from app.core import brex_profile as brex_profile_mod
from app.core import s1000d_schema, xml_safe
from app.core.brex_validation import validate_brex

log = structlog.get_logger("s1000d_extractor.validator")


def _v(severity: str, rule: str, message: str, path: str = "/") -> dict:
    return {"severity": severity, "rule": rule, "message": message, "path": path}


def validate_document(
    xml: str,
    *,
    issue: str,
    dm_type: str | None = None,
    brex_xml: str | None = None,
    brex_rules: dict | None = None,
    dm: dict | None = None,
) -> list[dict]:
    violations: list[dict] = []

    # 1. Well-formedness (toujours).
    try:
        xml_safe.fromstring(xml, allow_internal_dtd=True)
    except etree.XMLSyntaxError as exc:
        return [_v("error", "WELLFORMED", f"XML mal forme : {exc}")]

    # 2. XSD officiel (si installe pour l'Issue).
    try:
        violations.extend(
            s1000d_schema.validate_xsd(
                xml,
                issue,
                dm_type=dm_type,
                allow_internal_dtd=True,
            )
        )
    except Exception as exc:
        log.warning("xsd_validation_failed", issue=issue, error_type=type(exc).__name__, exc_info=True)
        # `warning`, pas `info` : "non validee" ne doit pas se lire comme "validee
        # avec une remarque benigne".
        violations.append(_v("warning", "XSD", f"Validation XSD NON EXECUTEE : {exc}"))

    # 3. BREX projet (si fourni).
    if brex_xml:
        try:
            brex_profile = brex_profile_mod.inspect_brex(brex_xml)
            violations.extend(
                validate_brex(
                    xml, brex_profile.rules, allow_internal_dtd=True
                )
            )
            for rule in brex_profile.unsupported_rules:
                violations.append(_v(
                    "warning",
                    "BREX_UNSUPPORTED",
                    f"Regle BREX {rule.rule_type} non appliquee : "
                    f"{rule.description or rule.rule_id or rule.rule_type}",
                    f"BREX/{rule.rule_id or rule.rule_type}",
                ))
        except Exception as exc:
            log.warning("brex_validation_failed", error_type=type(exc).__name__, exc_info=True)
            violations.append(_v("warning", "BREX", f"Validation BREX NON EXECUTEE : {exc}"))

    # 4. Regles client (BREX JSON) sur le DM lui-meme, si fournies.
    if brex_rules and dm is not None:
        from app.core.brex_rules import validate_dm_against_brex

        try:
            violations.extend(validate_dm_against_brex(dm, brex_rules))
        except Exception as exc:
            log.warning("client_brex_validation_failed", error_type=type(exc).__name__, exc_info=True)
            violations.append(
                _v("warning", "BREX_RULES", f"Regles client NON APPLIQUEES : {exc}")
            )

    return violations


def xsd_is_valid(violations: list[dict]) -> bool:
    """Return false unless the XML is well formed and its exact XSD check passed."""
    return not any(
        violation.get("rule") in {"XSD", "WELLFORMED"}
        for violation in violations
    )


def has_blocking_violation(violations: list[dict]) -> bool:
    """Only XSD/well-formedness failures and error-severity rules make a DM incomplete;
    warnings and provisional missing fields are reported but do not."""
    return not xsd_is_valid(violations) or any(
        violation.get("severity") == "error" for violation in violations
    )
