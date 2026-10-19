"""Apply parsed structure rules from a user-supplied BREX DM."""

from __future__ import annotations

from lxml import etree

from app.core import xml_safe
from app.core.brex import BrexRule


def _v(
    severity: str,
    rule: str,
    message: str,
    path: str,
    brex_rule: BrexRule | None = None,
) -> dict:
    violation = {"severity": severity, "rule": rule, "message": message, "path": path}
    if brex_rule is not None:
        if brex_rule.rule_id:
            violation["brex_rule_id"] = brex_rule.rule_id
        if brex_rule.severity_level:
            violation["brex_severity_level"] = brex_rule.severity_level
    return violation


def _xpath_value(value: object) -> str:
    if isinstance(value, etree._Element):
        return "".join(value.itertext()).strip()
    return str(value).strip()


def validate_brex(
    xml: str, rules: list[BrexRule], *, allow_internal_dtd: bool = False
) -> list[dict]:
    """Apply structure rules and report unsupported XPath/value forms explicitly."""
    if not rules:
        return []
    try:
        doc = xml_safe.fromstring(xml, allow_internal_dtd=allow_internal_dtd)
    except etree.XMLSyntaxError as exc:
        return [_v("error", "BREX", f"XML mal forme : {exc}", "/")]

    schema_uri = doc.get("{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation")
    out: list[dict] = []
    for rule in rules:
        if rule.rules_context and schema_uri != rule.rules_context:
            if not schema_uri:
                out.append(_v(
                    "warning", "BREX_CONTEXT_UNVERIFIABLE",
                    "Contexte BREX non verifiable : reference au schema du DM absente.",
                    rule.rules_context, rule,
                ))
            continue

        try:
            matches = doc.xpath(rule.object_path, namespaces=rule.namespaces)
        except etree.XPathError as exc:
            out.append(_v(
                "warning", "BREX_PATH_UNVERIFIABLE",
                f"Chemin BREX non evalue : {exc}", rule.object_path, rule,
            ))
            continue

        if rule.allowed_flag == "0":
            if matches:
                out.append(_v(
                    "error", "BREX",
                    f"Objet interdit present : {rule.object_use or rule.object_path}",
                    rule.object_path, rule,
                ))
            continue
        if rule.allowed_flag == "1" and not matches:
            out.append(_v(
                "error", "BREX",
                f"Objet obligatoire absent : {rule.object_use or rule.object_path}",
                rule.object_path, rule,
            ))
            continue
        if rule.allowed_flag not in {"1", "2"}:
            out.append(_v(
                "warning", "BREX_FLAG_UNSUPPORTED",
                f"Flag BREX non pris en charge : {rule.allowed_flag}",
                rule.object_path, rule,
            ))
            continue

        if not rule.object_values:
            continue
        if any(
            not value.value_allowed
            or value.value_tailoring != "closed"
            or value.value_form not in {None, "single"}
            for value in rule.object_values
        ):
            out.append(_v(
                "warning", "BREX_VALUE_UNSUPPORTED",
                "Forme ou tailoring de valeur BREX non pris en charge.",
                rule.object_path, rule,
            ))
            continue

        allowed_values = set(rule.values_allowed)
        for match in matches:
            actual = _xpath_value(match)
            if actual not in allowed_values:
                out.append(_v(
                    "error", "BREX_VALUE",
                    f"Valeur non autorisee : {actual}",
                    rule.object_path, rule,
                ))
    return out
