"""Read identifying and preview information from a user-supplied BREX DM."""

from __future__ import annotations

import codecs
import re
from dataclasses import dataclass
from html.entities import html5
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from lxml import etree

from app.core import xml_safe
from app.core.brex import BrexRule, parse_brex_root

_UNSUPPORTED_RULE_TYPES = {"nonContextRule", "notationRule", "snsRules"}
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_ISSUE_PATTERN = re.compile(r"S1000D[_-](\d+)[.-](\d+)", re.IGNORECASE)
_UNDEFINED_ENTITY = re.compile(r"Entity '([A-Za-z][A-Za-z0-9]+)' not defined")
_XML_ENCODING = re.compile(
    r"""<\?xml\b[^?]*\bencoding\s*=\s*(['"])([^'"]+)\1""",
    re.IGNORECASE,
)
_XML_DECLARATION = re.compile(r"^\s*<\?xml\b.*?\?>", re.IGNORECASE | re.DOTALL)
_NAMED_ENTITY = re.compile(r"&([A-Za-z][A-Za-z0-9]+);")
_XML_ENTITIES = {"amp", "apos", "gt", "lt", "quot"}


@dataclass(frozen=True)
class UnsupportedBrexRule:
    rule_type: str
    rule_id: str | None
    description: str


@dataclass(frozen=True)
class BrexProfileData:
    dmc: str
    dm_code: dict[str, str]
    issue: str | None
    schema_location: str | None
    rules: list[BrexRule]
    unsupported_rules: list[UnsupportedBrexRule]


def _localname(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def format_dmc(dm_code: dict[str, str]) -> str:
    parts = [
        dm_code.get("modelIdentCode", ""),
        dm_code.get("systemDiffCode", ""),
        dm_code.get("systemCode", ""),
        dm_code.get("subSystemCode", "") + dm_code.get("subSubSystemCode", ""),
        dm_code.get("assyCode", ""),
        dm_code.get("disassyCode", "") + dm_code.get("disassyCodeVariant", ""),
        dm_code.get("infoCode", "") + dm_code.get("infoCodeVariant", ""),
        dm_code.get("itemLocationCode", ""),
    ]
    return "DMC-" + "-".join(parts) if any(parts) else ""


def _is_brex_schema_location(value: str) -> bool:
    path = urlsplit(value).path or value
    return PurePosixPath(path.replace("\\", "/")).name.lower() == "brex.xsd"


def _brex_schema_location(root: etree._Element) -> str | None:
    no_namespace = root.get(f"{{{_XSI_NS}}}noNamespaceSchemaLocation", "").strip()
    if no_namespace and _is_brex_schema_location(no_namespace):
        return no_namespace
    schema_locations = root.get(f"{{{_XSI_NS}}}schemaLocation", "").split()
    return next(
        (
            schema_locations[index]
            for index in range(1, len(schema_locations), 2)
            if _is_brex_schema_location(schema_locations[index])
        ),
        None,
    )


def _inspect_brex_root(root: etree._Element) -> BrexProfileData:
    schema_location = _brex_schema_location(root)
    issue_match = _ISSUE_PATTERN.search(schema_location or "")
    issue = f"{issue_match.group(1)}.{issue_match.group(2)}" if issue_match else None
    dm_code_nodes = root.xpath(
        "./*[local-name()='identAndStatusSection']"
        "/*[local-name()='dmAddress']/*[local-name()='dmIdent']/*[local-name()='dmCode']"
    )
    dm_code = dict(dm_code_nodes[0].attrib) if dm_code_nodes else {}
    unsupported = [
        UnsupportedBrexRule(
            rule_type=_localname(node.tag),
            rule_id=node.get("id"),
            description=" ".join("".join(node.itertext()).split()),
        )
        for node in root.iter()
        if _localname(node.tag) in _UNSUPPORTED_RULE_TYPES
    ]
    return BrexProfileData(
        dmc=format_dmc(dm_code),
        dm_code=dm_code,
        issue=issue,
        schema_location=schema_location,
        rules=parse_brex_root(root),
        unsupported_rules=unsupported,
    )


def _decode_xml_upload(raw: bytes) -> str:
    if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        encoding = "utf-32"
    elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding = "utf-16"
    elif raw.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    elif raw.startswith(b"\x00<\x00?"):
        encoding = "utf-16-be"
    elif raw.startswith(b"<\x00?\x00"):
        encoding = "utf-16-le"
    elif raw.startswith(b"\x00\x00\x00<"):
        encoding = "utf-32-be"
    elif raw.startswith(b"<\x00\x00\x00"):
        encoding = "utf-32-le"
    else:
        prefix = raw[:512].decode("ascii", errors="ignore")
        declaration = _XML_ENCODING.search(prefix)
        encoding = declaration.group(2) if declaration else "utf-8"
    return raw.decode(encoding)


def _expand_html_character_entities(xml: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in _XML_ENTITIES:
            return match.group(0)
        value = html5.get(f"{name};")
        if value is None:
            return match.group(0)
        return "".join(f"&#x{ord(character):X};" for character in value)

    without_declaration = _XML_DECLARATION.sub("", xml, count=1)
    return _NAMED_ENTITY.sub(replace, without_declaration)


def inspect_brex(brex_xml: str | bytes) -> BrexProfileData:
    """Read a BREX DM without validating it against brex.xsd."""
    root = xml_safe.fromstring(brex_xml, allow_internal_dtd=True)
    return _inspect_brex_root(root)


def normalize_brex_upload(raw: bytes) -> tuple[str, BrexProfileData]:
    """Parse the XML's declared encoding and store a UTF-8 serialization."""
    try:
        root = xml_safe.fromstring(raw, allow_internal_dtd=True)
    except etree.XMLSyntaxError as exc:
        if not _UNDEFINED_ENTITY.search(str(exc)):
            raise
        expanded = _expand_html_character_entities(_decode_xml_upload(raw))
        root = xml_safe.fromstring(expanded, allow_internal_dtd=True)
    normalized = etree.tostring(
        root.getroottree(),
        encoding="utf-8",
        xml_declaration=True,
    ).decode("utf-8")
    return normalized, _inspect_brex_root(root)


def extract_brex_dm_code(brex_xml: str) -> dict[str, str]:
    """Extract the BREX DM's own dmCode for generated brexDmRef elements."""
    root = xml_safe.fromstring(brex_xml, allow_internal_dtd=True)
    nodes = root.xpath(
        "./*[local-name()='identAndStatusSection']"
        "/*[local-name()='dmAddress']/*[local-name()='dmIdent']/*[local-name()='dmCode']"
    )
    if not nodes:
        raise ValueError("Le DMC du BREX utilisateur est introuvable.")
    return dict(nodes[0].attrib)
