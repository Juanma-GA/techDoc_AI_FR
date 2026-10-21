"""Validation deterministe de Data Modules S1000D importes."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from lxml import etree

from app.core import s1000d_schema, xml_safe

_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_ISSUE_PATTERN = re.compile(r"S1000D[_-](\d+)[.-](\d+)", re.IGNORECASE)
_ISSUE_OVERRIDE_PATTERN = re.compile(r"(?:issue\s*)?(\d+)[.-](\d+)", re.IGNORECASE)


def validate_dm(
    xml: bytes,
    *,
    filename: str,
    issue_override: str | None = None,
) -> dict:
    """Inspecte un DM, choisit son XSD local et renvoie ses violations."""
    result = {
        "filename": filename,
        "dmc": "",
        "issue": None,
        "schema": None,
        "status": "invalid",
        "error_count": 0,
        "violations": [],
    }
    try:
        root = xml_safe.fromstring(xml, allow_internal_dtd=True)
    except etree.XMLSyntaxError as exc:
        line, column = exc.position
        result["violations"] = [{
            "severity": "error",
            "rule": "WELLFORMED",
            "message": f"XML mal formé : {exc}",
            "path": "/",
            "line": line or None,
            "column": column or None,
        }]
        result["error_count"] = 1
        return result

    result["dmc"] = _dmc(root)
    if _local_name(root.tag) != "dmodule":
        result["violations"] = [{
            "severity": "error",
            "rule": "ROOT",
            "message": "La racine XML doit être <dmodule>.",
            "path": f"/{_local_name(root.tag)}",
            "line": 1,
            "column": 1,
        }]
        result["error_count"] = 1
        return result

    detected_issue, schema = _schema_metadata(root)
    issue = _normalize_issue(issue_override) or detected_issue
    result["issue"] = issue
    result["schema"] = schema
    if issue is None:
        result["status"] = "needs_issue"
        result["message"] = "Issue S1000D non détectée; choisissez une version pour valider ce DM."
        return result

    if schema is None:
        schema = _infer_schema(root)
        result["schema"] = schema

    violations = s1000d_schema.validate_xsd(
        xml,
        issue,
        dm_type=schema,
        allow_internal_dtd=True,
    )
    result["violations"] = violations
    result["error_count"] = sum(v.get("severity") == "error" for v in violations)
    if result["error_count"]:
        result["status"] = "invalid"
    elif any(v.get("severity") in {"info", "warning"} for v in violations):
        result["status"] = "unverifiable"
    else:
        result["status"] = "valid"
    return result


def _schema_metadata(root: etree._Element) -> tuple[str | None, str | None]:
    schema_values = [
        root.get(f"{{{_XSI_NS}}}noNamespaceSchemaLocation", ""),
        root.get(f"{{{_XSI_NS}}}schemaLocation", ""),
    ]
    schema_text = " ".join(value for value in schema_values if value)
    issue_match = _ISSUE_PATTERN.search(schema_text)
    issue = f"{issue_match.group(1)}.{issue_match.group(2)}" if issue_match else None

    for token in schema_text.split():
        basename = PurePosixPath(token.replace("\\", "/")).name.lower()
        if basename.endswith(".xsd"):
            return issue, basename.removesuffix(".xsd")
    return issue, None


def _normalize_issue(value: str | None) -> str | None:
    if not value:
        return None
    match = _ISSUE_OVERRIDE_PATTERN.fullmatch(value.strip())
    return f"{match.group(1)}.{match.group(2)}" if match else None


def _infer_schema(root: etree._Element) -> str:
    if root.xpath(".//*[local-name()='procedure']"):
        return "proced"
    if root.xpath(".//*[local-name()='ipd']"):
        return "ipd"
    return "descript"


def _dmc(root: etree._Element) -> str:
    nodes = root.xpath(".//*[local-name()='dmCode']")
    if not nodes:
        return ""
    attrs = nodes[0].attrib
    parts = [
        attrs.get("modelIdentCode", ""),
        attrs.get("systemDiffCode", ""),
        attrs.get("systemCode", ""),
        attrs.get("subSystemCode", "") + attrs.get("subSubSystemCode", ""),
        attrs.get("assyCode", ""),
        attrs.get("disassyCode", "") + attrs.get("disassyCodeVariant", ""),
        attrs.get("infoCode", "") + attrs.get("infoCodeVariant", ""),
        attrs.get("itemLocationCode", ""),
    ]
    return "DMC-" + "-".join(parts) if any(parts) else ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]