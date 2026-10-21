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
) -> dict[str, object]:
    violation: dict[str, object] = {
        "severity": severity,
        "rule": rule,
        "message": message,
        "path": path,
    }
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


class CompiledBrexValidator:
    """Reuse compiled XPath expressions when candidate mappings are trialled."""

    def __init__(self, rules: list[BrexRule]) -> None:
        self.rules = tuple(rules)
        self._xpaths: list[etree.XPath | None] = []
        self._xpath_errors: list[str | None] = []
        for rule in rules:
            try:
                xpath = (
                    etree.XPath(rule.object_path, namespaces=rule.namespaces)
                    if rule.namespaces
                    else etree.XPath(rule.object_path)
                )
                self._xpaths.append(xpath)
                self._xpath_errors.append(None)
            except etree.XPathError as exc:
                self._xpaths.append(None)
                self._xpath_errors.append(str(exc))

    def validate(
        self, xml: str, *, allow_internal_dtd: bool = False
    ) -> list[dict[str, object]]:
        if not self.rules:
            return []
        try:
            doc = xml_safe.fromstring(xml, allow_internal_dtd=allow_internal_dtd)
        except etree.XMLSyntaxError as exc:
            return [_v("error", "BREX", f"XML mal forme : {exc}", "/")]

        schema_uri = doc.get(
            "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"
        )
        out: list[dict[str, object]] = []
        for rule, xpath, xpath_error in zip(
            self.rules, self._xpaths, self._xpath_errors, strict=True
        ):
            if rule.rules_context and schema_uri != rule.rules_context:
                if not schema_uri:
                    out.append(_v(
                        "warning", "BREX_CONTEXT_UNVERIFIABLE",
                        "Contexte BREX non verifiable : reference au schema du DM absente.",
                        rule.rules_context, rule,
                    ))
                continue

            if xpath is None:
                out.append(_v(
                    "warning", "BREX_PATH_UNVERIFIABLE",
                    f"Chemin BREX non evalue : {xpath_error or 'XPath invalide'}",
                    rule.object_path, rule,
                ))
                continue
            try:
                matches = xpath(doc)
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
            unsupported_values = [
                value for value in rule.object_values
                if value.support_reason is not None
            ]
            if unsupported_values:
                invalid_pattern = any(
                    value.support_reason == "invalid_value_pattern"
                    for value in unsupported_values
                )
                message = (
                    "Motif de valeur BREX invalide."
                    if invalid_pattern
                    else "Forme ou tailoring de valeur BREX non pris en charge."
                )
                out.append(_v(
                    "warning", "BREX_VALUE_UNSUPPORTED", message, rule.object_path, rule,
                ))
                continue

            for match in matches:
                actual = _xpath_value(match)
                if not any(value.allows(actual) for value in rule.object_values):
                    out.append(_v(
                        "error", "BREX_VALUE",
                        f"Valeur non autorisee : {actual}",
                        rule.object_path, rule,
                    ))
        return out


def compile_brex_validator(rules: list[BrexRule]) -> CompiledBrexValidator:
    return CompiledBrexValidator(rules)


def validate_brex(
    xml: str, rules: list[BrexRule], *, allow_internal_dtd: bool = False
) -> list[dict[str, object]]:
    """Apply structure rules and report unsupported XPath/value forms explicitly."""
    return compile_brex_validator(rules).validate(
        xml, allow_internal_dtd=allow_internal_dtd
    )
