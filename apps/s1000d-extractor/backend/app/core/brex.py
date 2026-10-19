"""Parse machine-readable structure rules from a user-supplied BREX DM."""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from app.core import xml_safe


@dataclass(frozen=True)
class BrexObjectValue:
    value_allowed: str | None
    value_text: str
    value_form: str | None = None
    value_tailoring: str = "closed"


@dataclass
class BrexRule:
    object_path: str
    allowed_flag: str
    object_use: str
    object_values: list[BrexObjectValue] = field(default_factory=list)
    rule_id: str | None = None
    rules_context: str | None = None
    context_id: str | None = None
    severity_level: str | None = None
    namespaces: dict[str, str] = field(default_factory=dict)

    @property
    def values_allowed(self) -> list[str]:
        return [
            value.value_allowed
            for value in self.object_values
            if value.value_allowed is not None
        ]

    @property
    def supported(self) -> bool:
        if self.allowed_flag not in {"0", "1", "2"}:
            return False
        if any(
            not value.value_allowed
            or value.value_tailoring != "closed"
            or value.value_form not in {None, "single"}
            for value in self.object_values
        ):
            return False
        try:
            _compile_xpath(self.object_path, self.namespaces)
        except etree.XPathError:
            return False
        return True


def _localname(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _direct_child(parent: etree._Element, local: str) -> etree._Element | None:
    return next((child for child in parent if _localname(child.tag) == local), None)


def _text(element: etree._Element | None) -> str:
    return "".join(element.itertext()).strip() if element is not None else ""


def _compile_xpath(expression: str, namespaces: dict[str, str]) -> etree.XPath:
    if namespaces:
        return etree.XPath(expression, namespaces=namespaces)
    return etree.XPath(expression)


def parse_brex_root(root: etree._Element) -> list[BrexRule]:
    """Extract structure rules and their schema context from a parsed BREX DM."""
    rules: list[BrexRule] = []
    namespaces = {key: value for key, value in root.nsmap.items() if key and value}
    for rule_element in root.iter():
        if _localname(rule_element.tag) != "structureObjectRule":
            continue
        path_element = _direct_child(rule_element, "objectPath")
        object_path = _text(path_element)
        if not object_path:
            continue

        context_element = next(
            (
                ancestor for ancestor in rule_element.iterancestors()
                if _localname(ancestor.tag) == "contextRules"
            ),
            None,
        )
        values = [
            BrexObjectValue(
                value_allowed=child.get("valueAllowed"),
                value_text=_text(child),
                value_form=child.get("valueForm"),
                value_tailoring=child.get("valueTailoring", "closed"),
            )
            for child in rule_element
            if _localname(child.tag) == "objectValue"
        ]
        rules.append(BrexRule(
            object_path=object_path,
            allowed_flag=path_element.get("allowedObjectFlag") or "2",
            object_use=_text(_direct_child(rule_element, "objectUse")),
            object_values=values,
            rule_id=rule_element.get("id"),
            rules_context=(
                context_element.get("rulesContext", "").strip() or None
                if context_element is not None
                else None
            ),
            context_id=context_element.get("id") if context_element is not None else None,
            severity_level=rule_element.get("brSeverityLevel"),
            namespaces=namespaces,
        ))
    return rules


def parse_brex(brex_xml: str) -> list[BrexRule]:
    """Extract structure rules without validating the user BREX against brex.xsd."""
    return parse_brex_root(xml_safe.fromstring(brex_xml, allow_internal_dtd=True))
