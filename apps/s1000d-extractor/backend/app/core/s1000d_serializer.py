"""Serialiseur : IR resolu -> squelette XML contraint par les XSD locaux (lxml).

Les donnees metier absentes utilisent des valeurs provisoires acceptees par le
XSD et sont reprises dans le recapitulatif des champs a confirmer. Le XML reste
telechargeable si du contenu source ne peut pas etre represente.

Noms d'elements conformes aux XSD locaux Issue 4.1 / 4.2 :
- bloc d'identification : `identAndStatusSection` (`dmAddress` + `dmStatus`,
  le `brexDmRef` vit dans `dmStatus`) ;
- listes : `randomList`/`sequentialList` > `listItem` > `para` ;
- procedure : `procedure` > `mainProcedure` > `proceduralStep` > `para` ;
- admonitions : `warning`/`caution` > `warningAndCautionPara`, `note` > `notePara` ;
- figure : `figure` > `title` + `graphic[@infoEntityIdent]` (PAS `boardno`, legacy 2.x) ;
- tableaux : modele CALS `table` > `tgroup` > `tbody` > `row` > `entry` > `para`.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from lxml import etree

from app.core import xml_safe
from app.core.dm_header import DEFAULT_HEADER_TEMPLATE
from app.core.ir import InlineRun, IRNode
from app.core.pmc import parse_dmc
from app.core.s1000d_codes import emphasis_code_for_style, get_code
from app.core.s1000d_ids import normalize_dm_ids
from app.core.xsd_model import ConstraintReport, load_xsd_model

_BANNER = (
    " Squelette structurel best-effort genere par s1000d extractor. "
    "DMC / SNS / applicabilite / securite / ICN et contenu metier a confirmer "
    "avant publication (voir le recapitulatif des champs manquants). "
)
_MISSING_DATA_COMMENT_PREFIX = "A REMPLACER AVANT PUBLICATION:"

# Caracteres de controle interdits en XML 1.0 (le texte d'un PDF en contient
# souvent : form feed, NUL...). lxml leve une ValueError -> 500 cote API. On les
# retire au seuil de la serialisation, une fois pour toutes.
_INVALID_XML_CHARS = re.compile(r"[^\u0009\u000A\u000D\u0020-\uD7FF\uE000-\uFFFD]")
# Nom d'element XML valide (les candidats viennent d'un override humain / LLM).
_NCNAME = re.compile(r"^[A-Za-z_][\w.\-]*$")
_GRAPHIC_EXTENSION = re.compile(r"\.(?:jpe?g|png)$", re.IGNORECASE)
_GRAPHIC_NOTATION = {".jpg": "jpg", ".jpeg": "jpg", ".png": "png"}
_ICN_TITLE_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_-])ICN-[A-Za-z0-9_.-]+?(?:\.(?:jpe?g|png))?"
    r"(?=$|[\s,;|)\]}])",
    re.IGNORECASE,
)
_FIGURE_TITLE_PREFIX = re.compile(
    r"^\s*(?:figure|fig\.?|illustration)\s+\d+(?:[.\-]\d+)*"
    r"(?:\s*[:.\-\u2013\u2014]\s*|\s+)",
    re.IGNORECASE,
)
_NUMBERED_TITLE_PREFIX = re.compile(
    r"^\s*\d+(?:\.\d+)*(?:\s*[.)\-\u2013\u2014:]\s*|\s+)",
)
_TRAILING_PUNCTUATION = re.compile(r"^[\s\u00a0\u202f]*[:;,.!?]+$")
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_XLINK_NS = "http://www.w3.org/1999/xlink"
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_DC_NS = "http://www.purl.org/dc/elements/1.1/"
_SCHEMA_NAMES = {
    "descriptive": "descript.xsd",
    "description": "descript.xsd",
    "procedural": "proced.xsd",
    "procedure": "proced.xsd",
    "ipd": "ipd.xsd",
}
_DM_TYPE_ALIASES = {
    "descriptive": "descriptive",
    "description": "descriptive",
    "descript": "descriptive",
    "procedural": "procedural",
    "procedure": "procedural",
    "proced": "procedural",
    "ipd": "ipd",
}
_DM_CODE_DEFAULTS = {
    "assyCode": "ZZ",
    "disassyCode": "ZZ",
    "disassyCodeVariant": "Z",
    "infoCode": "ZZZ",
    "infoCodeVariant": "Z",
    "itemLocationCode": "T",
    "modelIdentCode": "ZZ",
    "subSubSystemCode": "Z",
    "subSystemCode": "Z",
    "systemCode": "ZZ",
    "systemDiffCode": "Z",
}
_DM_FIELD_NAMES = {
    "modelIdentCode": "model_ident_code",
    "systemDiffCode": "system_diff_code",
    "systemCode": "system_code",
    "subSystemCode": "sub_system_code",
    "subSubSystemCode": "sub_sub_system_code",
    "assyCode": "assy_code",
    "disassyCode": "disassy_code",
    "disassyCodeVariant": "disassy_code_variant",
    "infoCode": "info_code",
    "infoCodeVariant": "info_code_variant",
    "itemLocationCode": "item_location_code",
}

_INTERNAL_REF_CODES = {
    "figure": "irtt01",
    "table": "irtt02",
    "paragraph": "irtt07",
    "step": "irtt08",
    "graphic": "irtt09",
    "section": "irtt07",
}
_MIXED_CONTENT_TAGS = frozenset({
    "para",
    "notePara",
    "warningAndCautionPara",
    "attentionListItemPara",
})
_LAYOUT_NOISE_ZONES = frozenset({"header", "footer", "cover", "toc"})
_FIGURE_LABEL_RE = re.compile(
    r"^\s*(?:figure|fig\.?|illustration)\s*(\d+(?:[.\-]\d+)*)\b",
    re.IGNORECASE,
)
_TABLE_LABEL_RE = re.compile(
    r"^\s*(?:table|tableau)\s*(\d+(?:[.\-]\d+)*)\b",
    re.IGNORECASE,
)
_SECTION_LABEL_RE = re.compile(r"^\s*(\d+(?:[.\-]\d+)*)\b")
_PROCEDURE_REQUIREMENT_HEADINGS = {
    "conditions": re.compile(
        r"\b(?:preconditions?|prerequisites?|required conditions?|"
        r"conditions? (?:prealables?|requises?|a respecter))\b"
    ),
    "personnel": re.compile(r"\b(?:required personnel|personnel(?: requis| necessaire)?|manpower)\b"),
    "support": re.compile(
        r"\b(?:support equipment|special tools?|tools?|tooling|outillage|"
        r"outils?(?: necessaires?| requis?)?)\b"
    ),
    "supplies": re.compile(r"\b(?:supplies|consumables?|fournitures?|consommables?)\b"),
    "spares": re.compile(r"\b(?:spares?|spare parts|pieces? (?:de )?rechange)\b"),
    "safety": re.compile(r"\b(?:safety(?: requirements?)?|security requirements?|securite|precautions?)\b"),
}


def _normalize_dm_type(dm_type: str) -> str:
    normalized = _DM_TYPE_ALIASES.get((dm_type or "").lower())
    if normalized is None:
        raise ValueError(f"Type de DM non pris en charge par le generateur XSD : {dm_type}.")
    return normalized
_PRELIMINARY_CONTAINER_TITLES = {
    "preliminary requirements",
    "preliminary requisites",
    "exigences preliminaires",
}
_NO_REQUIREMENT_RE = re.compile(
    r"^(?:no\b|none\b|not required\b|not applicable\b|"
    r"aucun(?:e|s|es)?\b|pas de\b|sans\b)"
)


@dataclass(frozen=True)
class ReferenceTarget:
    kind: str
    label: str
    target_id: str
    target_type: str
    dm_id: str = ""
    dmc: str = ""


@dataclass
class SerializationDiagnostics:
    xsd_violations: list[dict] = field(default_factory=list)
    provisional_fields: list[str] = field(default_factory=list)


ReferenceIndex = dict[tuple[str, str], list[ReferenceTarget]]


def xml_text(value: str | None) -> str:
    """Texte utilisable comme contenu XML (caracteres de controle retires)."""
    return _INVALID_XML_CHARS.sub("", value or "")


def _canonical_ref_label(value: str) -> str:
    return re.sub(r"[^0-9]+", ".", value or "").strip(".")


def _reference_id(prefix: str, node_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", node_id or "").strip("-")
    if not safe:
        safe = "node"
    if not re.match(r"^[A-Za-z_]", safe):
        safe = f"{prefix}-{safe}"
    return f"{prefix}-{safe}"


def _labels_for_text(kind: str, text: str) -> list[str]:
    pattern = {
        "figure": _FIGURE_LABEL_RE,
        "table": _TABLE_LABEL_RE,
        "section": _SECTION_LABEL_RE,
    }.get(kind)
    if pattern is None:
        return []
    match = pattern.match(text or "")
    if not match:
        return []
    return [_canonical_ref_label(match.group(1))]


def _add_reference_target(index: ReferenceIndex, target: ReferenceTarget) -> None:
    if not target.label:
        return
    key = (target.kind, target.label)
    index.setdefault(key, []).append(target)


def _content_nodes(root: IRNode) -> list[IRNode]:
    nodes: list[IRNode] = []

    def walk(node: IRNode) -> None:
        for child in node.children:
            if child.zone in _LAYOUT_NOISE_ZONES or (
                child.kind == "figure" and child.is_pictogram
            ):
                continue
            nodes.append(child)
            walk(child)

    walk(root)
    return nodes


def content_node_count(root: IRNode, kind: str) -> int:
    return sum(node.kind == kind for node in _content_nodes(root))


def build_reference_index(
    documents: Sequence[tuple[str, IRNode, Mapping[str, object] | None]],
) -> ReferenceIndex:
    """Index visible reference targets with the IDs emitted in each DM."""
    index: ReferenceIndex = {}
    for dm_id, root, metadata in documents:
        metadata = metadata or {}
        dmc = str(metadata.get("dmc") or "")
        dm_type = _normalize_dm_type(str(metadata.get("dm_type") or "descriptive"))
        issue = str(metadata.get("issue") or "4.2")
        content = _build_content(
            root,
            dm_type,
            {"figure": 0, "table": 0, "section": 0},
            reference_index={},
            current_dm_id=dm_id,
        )
        load_xsd_model(issue, dm_type).constrain(content)
        normalize_dm_ids(content)

        targets_by_kind = {
            "figure": list(content.iter("figure")),
            "table": list(content.iter("table")),
            "section": [
                element for element in content.iter()
                if element.tag in {"proceduralStep", "levelledPara"}
            ],
        }
        used_target_ids: set[str] = set()
        nodes = _content_nodes(root)
        for position, node in enumerate(nodes):
            kind = node.kind if node.kind in {"section", "figure", "table"} else ""
            if not kind:
                continue
            labels = _labels_for_text(kind, node.text)
            if kind == "table" and not labels:
                nearby_labels = [
                    (
                        abs(candidate_position - position),
                        _labels_for_text("table", candidate.text),
                    )
                    for candidate_position, candidate in enumerate(
                        nodes[max(0, position - 3):position + 4],
                        start=max(0, position - 3),
                    )
                    if candidate is not node
                    and candidate.page == node.page
                    and _labels_for_text("table", candidate.text)
                ]
                if nearby_labels:
                    labels = min(nearby_labels, key=lambda item: item[0])[1]
            if not labels:
                continue

            expected_title = (
                clean_figure_title(node.text) or "A REMPLACER"
                if kind == "figure"
                else clean_title(node.text) or None
            )
            target = next(
                (
                    element for element in targets_by_kind[kind]
                    if element.get("id") not in used_target_ids
                    and element.findtext("title") == expected_title
                ),
                None,
            )
            if target is None:
                continue
            target_id = target.get("id")
            if not target_id:
                continue
            used_target_ids.add(target_id)
            target_type = (
                _INTERNAL_REF_CODES["step"]
                if target.tag == "proceduralStep"
                else _INTERNAL_REF_CODES[kind]
            )
            for label in labels:
                _add_reference_target(index, ReferenceTarget(
                    kind=kind,
                    label=label,
                    target_id=target_id,
                    target_type=target_type,
                    dm_id=dm_id,
                    dmc=dmc,
                ))
    return index


def _resolve_reference(
    index: ReferenceIndex,
    ref: Mapping[str, object],
    current_dm_id: str,
) -> ReferenceTarget | None:
    kind = str(ref.get("target_kind") or "section")
    label = _canonical_ref_label(str(ref.get("target") or ""))
    candidates = index.get((kind, label), [])
    if not candidates:
        return None
    local = [candidate for candidate in candidates if candidate.dm_id == current_dm_id]
    if len(local) == 1:
        return local[0]
    return candidates[0] if len(candidates) == 1 else None


def clean_title(value: str | None) -> str:
    """Retire les numeros editoriaux des titres emis dans le DM final."""
    title = xml_text(value).strip()
    title = _FIGURE_TITLE_PREFIX.sub("", title)
    return _NUMBERED_TITLE_PREFIX.sub("", title).strip()


def clean_figure_title(value: str | None) -> str:
    title = _ICN_TITLE_TOKEN.sub("", clean_title(value))
    title = re.sub(r"\(\s*\)|\[\s*\]", "", title)
    title = re.sub(r"\s+([,.;:!?])", r"\1", title)
    return re.sub(r"\s+", " ", title).strip(" \t\u00a0,;:\u2013\u2014-")


def _safe_element(name: str, fallback: str) -> str:
    return name if _NCNAME.match(name or "") else fallback


def _top_element(node: IRNode, fallback: str) -> str:
    element = node.candidates[0].element if node.candidates else fallback
    return _safe_element(element, fallback)


def _graphic_ident(icn: str) -> str:
    return _GRAPHIC_EXTENSION.sub("", xml_text(icn))


def _figure_icns(node: IRNode) -> list[str]:
    names = list(node.icns)
    if node.icn and node.icn not in names:
        names.insert(0, node.icn)
    return names


def _doctype(root: IRNode, dmodule: etree._Element | None = None) -> str:
    """Construit la DTD interne qui declare les fichiers graphiques du DM."""
    declarations: list[str] = []
    declared: set[str] = set()
    placeholder_ident = "ICN-ZZZ-00000"
    for node in root.walk():
        if node.kind != "figure" or node.is_pictogram:
            continue
        if not _figure_icns(node) and placeholder_ident not in declared:
            declarations.append(
                f'<!ENTITY {placeholder_ident} SYSTEM "{placeholder_ident}.jpg" NDATA jpg>'
            )
            declared.add(placeholder_ident)
        for icn in _figure_icns(node):
            filename = xml_text(icn)
            ident = _graphic_ident(filename)
            if not filename or ident in declared or not _NCNAME.fullmatch(ident):
                continue
            declared.add(ident)
            suffix = re.search(r"\.[^.]+$", filename)
            notation = _GRAPHIC_NOTATION.get(suffix.group(0).lower(), "jpg") if suffix else "jpg"
            declarations.append(
                f'<!ENTITY {ident} SYSTEM "{filename}" NDATA {notation}>'
            )
    if dmodule is not None:
        for graphic in dmodule.iter("graphic"):
            ident = graphic.get("infoEntityIdent", "")
            if ident and ident not in declared and _NCNAME.fullmatch(ident):
                declarations.append(
                    f'<!ENTITY {ident} SYSTEM "{ident}.jpg" NDATA jpg>'
                )
                declared.add(ident)
    declarations.append(
        '<!ENTITY % ISOEntities PUBLIC "ISO 8879-1986//ENTITIES ISO Character Entities 20030531//EN//XML" "ent/ISOEntities">'
    )
    return "<!DOCTYPE dmodule [\n" + "\n".join(declarations) + "\n]>"


def _schema_location(issue: str, dm_type: str) -> str:
    issue_path = xml_text(issue).replace(".", "-")
    schema_name = _SCHEMA_NAMES.get((dm_type or "descriptive").lower(), "descript.xsd")
    return f"http://www.s1000d.org/S1000D_{issue_path}/xml_schema_flat/{schema_name}"


def _dm_code(metadata: Mapping[str, object] | None) -> dict[str, str]:
    data = metadata or {}
    values = dict(_DM_CODE_DEFAULTS)
    parsed = parse_dmc(str(data.get("dmc") or ""))
    if parsed:
        values.update(parsed)
    for xml_name, field_name in _DM_FIELD_NAMES.items():
        value = data.get(field_name)
        if value:
            values[xml_name] = str(value).strip()
    return {key: xml_text(value) for key, value in values.items()}


def _missing_dm_code_fields(metadata: Mapping[str, object] | None) -> list[str]:
    data = metadata or {}
    if parse_dmc(str(data.get("dmc") or "")):
        return []
    base_path = "/dmodule/identAndStatusSection/dmAddress/dmIdent/dmCode"
    return [
        f"{base_path}/@{xml_name} (DMC source a renseigner)"
        for xml_name, field_name in _DM_FIELD_NAMES.items()
        if not data.get(field_name)
    ]


def _header_provisional_fields(
    template: Mapping[str, object] | None,
    metadata: Mapping[str, object] | None,
) -> list[str]:
    data = template or DEFAULT_HEADER_TEMPLATE
    dm_data = metadata or {}
    fields = [
        "/dmodule/identAndStatusSection/dmAddress/dmIdent/issueInfo/@inWork (valeur provisoire)",
        "/dmodule/identAndStatusSection/dmAddress/dmIdent/issueInfo/@issueNumber (valeur provisoire)",
    ]
    for name in ("techName", "infoName"):
        field_name = "tech_name" if name == "techName" else "info_name"
        if not dm_data.get(field_name):
            fields.append(
                f"/dmodule/identAndStatusSection/dmAddress/dmAddressItems/dmTitle/{name} (valeur provisoire)"
            )
    security = data.get("security") or {}
    if security.get("securityClassification") == DEFAULT_HEADER_TEMPLATE["security"]["securityClassification"]:
        fields.append(
            "/dmodule/identAndStatusSection/dmStatus/security/@securityClassification (valeur provisoire)"
        )
    language = data.get("language") or {}
    if language.get("countryIsoCode") == "FR":
        fields.append("/dmodule/identAndStatusSection/dmAddress/dmIdent/language/@countryIsoCode (valeur provisoire)")
    if language.get("languageIsoCode") == "fr":
        fields.append("/dmodule/identAndStatusSection/dmAddress/dmIdent/language/@languageIsoCode (valeur provisoire)")
    return fields


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().casefold()
    return any(marker in normalized for marker in (
        "a remplacer", "example organization", "unverified",
    ))


def _collect_missing_data_fields(
    root: etree._Element,
    extra_fields: Sequence[str] = (),
) -> list[str]:
    missing = [str(field).strip() for field in extra_fields if str(field).strip()]
    tree = root.getroottree()
    for node in root.iter():
        if isinstance(node, etree._Comment):
            text = (node.text or "").strip()
            if text.startswith(_MISSING_DATA_COMMENT_PREFIX):
                summary = text[len(_MISSING_DATA_COMMENT_PREFIX):].strip()
                missing.extend(field.strip() for field in summary.split(";") if field.strip())
                continue
            if _is_placeholder(text):
                missing.append(f"Commentaire XML: {text}")
            continue
        if not isinstance(node.tag, str):
            continue
        path = tree.getpath(node)
        if etree.QName(node).localname == "unverified":
            missing.append(f"{path} (assurance qualité à valider)")
        for name, value in node.attrib.items():
            local_name = etree.QName(name).localname
            if _is_placeholder(value) or (local_name == "enterpriseCode" and value == "EX"):
                missing.append(f"{path}/@{local_name}")
        text = (node.text or "").strip()
        if _is_placeholder(text):
            missing.append(f"{path}/text()")
        elif etree.QName(node).localname == "simplePara" and text.casefold() == "all" and "/applic" in path:
            missing.append(f"{path}/text() (applicabilité à confirmer)")
    return list(dict.fromkeys(missing))


def missing_data_fields(xml: str, extra_fields: Sequence[str] = ()) -> list[str]:
    root = xml_safe.fromstring(xml, allow_internal_dtd=True)
    return _collect_missing_data_fields(root, extra_fields)


def _text(value: object, fallback: str = "") -> str:
    return xml_text(str(value)) if value is not None else fallback


def _company(parent: etree._Element, name: str, data: Mapping[str, object]) -> None:
    company = etree.SubElement(parent, name, enterpriseCode=_text(data.get("enterpriseCode"), "EX"))
    etree.SubElement(company, "enterpriseName").text = _text(
        data.get("enterpriseName"), "A REMPLACER"
    )


def _emit_data_restrictions(parent: etree._Element, template: Mapping[str, object]) -> None:
    restrictions = etree.SubElement(parent, "dataRestrictions")
    instructions = template.get("restrictionInstructions") or {}
    instruction_el = etree.SubElement(restrictions, "restrictionInstructions")
    etree.SubElement(instruction_el, "dataDistribution").text = _text(
        instructions.get("dataDistribution")
    )
    export = instructions.get("exportControl") or {}
    statement = (export.get("exportRegistrationStmt") or {}) if isinstance(export, dict) else {}
    statement_el = etree.SubElement(etree.SubElement(instruction_el, "exportControl"), "exportRegistrationStmt")
    etree.SubElement(statement_el, "simplePara").text = _text(statement.get("simplePara"))
    for field in ("dataHandling", "dataDestruction", "dataDisclosure"):
        etree.SubElement(instruction_el, field).text = _text(instructions.get(field))

    info = template.get("restrictionInfo") or {}
    info_el = etree.SubElement(restrictions, "restrictionInfo")
    copyright_data = info.get("copyright") or {}
    copyright_el = etree.SubElement(info_el, "copyright")
    paragraphs = copyright_data.get("copyrightPara") or []
    if isinstance(paragraphs, str):
        paragraphs = [paragraphs]
    for paragraph in paragraphs:
        etree.SubElement(copyright_el, "copyrightPara").text = _text(paragraph)
    etree.SubElement(info_el, "dataConds").text = _text(info.get("dataConds"))


def _emit_dm_status(parent: etree._Element, template: Mapping[str, object]) -> None:
    status = etree.SubElement(parent, "dmStatus", issueType="new")
    security = template.get("security") or {}
    etree.SubElement(status, "security", securityClassification=_text(
        security.get("securityClassification"), "02"
    ))
    _emit_data_restrictions(status, template.get("dataRestrictions") or {})
    _company(status, "responsiblePartnerCompany", template.get("responsiblePartnerCompany") or {})
    _company(status, "originator", template.get("originator") or {})
    applic = etree.SubElement(status, "applic")
    display = etree.SubElement(applic, "displayText")
    etree.SubElement(display, "simplePara").text = _text(template.get("applicability"), "A REMPLACER")

    brex = etree.SubElement(status, "brexDmRef")
    dm_ref = etree.SubElement(brex, "dmRef")
    dm_ref_ident = etree.SubElement(dm_ref, "dmRefIdent")
    brex_data = template.get("brexDmRef") or {}
    brex_code = brex_data.get("dmCode") if isinstance(brex_data, dict) else {}
    etree.SubElement(dm_ref_ident, "dmCode", **{
        str(key): _text(value) for key, value in (brex_code or {}).items()
        if _NCNAME.fullmatch(str(key))
    })
    assurance_name = _safe_element(_text(template.get("qualityAssurance"), "unverified"), "unverified")
    etree.SubElement(etree.SubElement(status, "qualityAssurance"), assurance_name)


def _emit_header(
    dmodule: etree._Element,
    *,
    issue: str,
    dm_type: str,
    title: str,
    dm_metadata: Mapping[str, object] | None,
    header_template: Mapping[str, object] | None,
    created_at: datetime | None,
) -> None:
    metadata = dm_metadata or {}
    template = header_template or DEFAULT_HEADER_TEMPLATE
    ident = etree.SubElement(dmodule, "identAndStatusSection")
    address = etree.SubElement(ident, "dmAddress")
    dm_ident = etree.SubElement(address, "dmIdent")
    etree.SubElement(dm_ident, "dmCode", **_dm_code(metadata))
    language = template.get("language") or {}
    etree.SubElement(dm_ident, "language", countryIsoCode=_text(language.get("countryIsoCode"), "FR"), languageIsoCode=_text(language.get("languageIsoCode"), "fr"))
    etree.SubElement(dm_ident, "issueInfo", inWork="00", issueNumber="001")
    items = etree.SubElement(address, "dmAddressItems")
    now = created_at or datetime.now(UTC)
    etree.SubElement(items, "issueDate", day=f"{now.day:02d}", month=f"{now.month:02d}", year=str(now.year))
    dm_title = etree.SubElement(items, "dmTitle")
    fallback_title = _text(title) or _text(metadata.get("title")) or "A REMPLACER"
    etree.SubElement(dm_title, "techName").text = _text(metadata.get("tech_name")) or fallback_title
    etree.SubElement(dm_title, "infoName").text = _text(metadata.get("info_name")) or fallback_title
    _emit_dm_status(ident, template)


def _alt_comment(node: IRNode) -> str | None:
    if len(node.candidates) > 1:
        alts = ", ".join(f"{c.element}({c.score:.2f})" for c in node.candidates[1:])
        return f" alt: {alts} "
    return None


def _comment(text: str) -> etree._Comment:
    """Commentaire XML sur : pas de `--` (interdit) ni de caractere de controle."""
    return etree.Comment(xml_text(text).replace("--", "- -"))


def _run_value(run: InlineRun | dict, name: str, default: object = "") -> object:
    if isinstance(run, dict):
        return run.get(name, default)
    return getattr(run, name, default)


def _run_emphasis_codes(run: InlineRun | dict) -> list[str]:
    if not str(_run_value(run, "text", "")).strip():
        return []
    codes: list[str] = []
    for style in ("bold", "italic", "underline", "overline", "strikethrough"):
        if not bool(_run_value(run, style, False)):
            continue
        code = emphasis_code_for_style(style)
        if code and code not in codes and get_code("emphasisType", code):
            codes.append(code)
    return codes


def _append_inline_text(parent: etree._Element, text: str) -> None:
    safe_text = xml_text(text)
    if not safe_text:
        return
    if len(parent):
        last = parent[-1]
        last.tail = (last.tail or "") + safe_text
    else:
        parent.text = (parent.text or "") + safe_text


def _append_emphasis(parent: etree._Element, code: str, text: str) -> None:
    safe_text = xml_text(text)
    if not safe_text:
        return
    if len(parent):
        last = parent[-1]
        separator = last.tail or ""
        if (
            last.tag == "emphasis"
            and last.get("emphasisType") == code
            and not separator.strip()
        ):
            last.text = (last.text or "") + separator + safe_text
            last.tail = None
            return
    emphasis = etree.SubElement(parent, "emphasis", emphasisType=code)
    emphasis.text = safe_text


def _append_nested_emphasis(
    parent: etree._Element,
    codes: list[str],
    text: str,
) -> etree._Element:
    current = parent
    for code in codes:
        current = etree.SubElement(current, "emphasis", emphasisType=code)
    current.text = xml_text(text)
    return parent[-1]


def _inline_content(
    parent: etree._Element,
    text: str,
    runs: list[InlineRun] | None = None,
) -> None:
    usable_runs = runs or []
    if usable_runs and "".join(str(_run_value(run, "text", "")) for run in usable_runs) != text:
        usable_runs = []
    if usable_runs and not len(parent) and parent.text is None:
        parent.text = ""
    if not usable_runs:
        _append_inline_text(parent, text)
        return
    last_nested_emphasis: tuple[tuple[str, ...], etree._Element] | None = None
    bold_code = emphasis_code_for_style("bold")
    for run in usable_runs:
        run_text = str(_run_value(run, "text", ""))
        codes = _run_emphasis_codes(run)
        if (
            last_nested_emphasis is not None
            and bold_code is not None
            and last_nested_emphasis[0][0] == bold_code
            and codes == list(last_nested_emphasis[0][1:])
            and _TRAILING_PUNCTUATION.fullmatch(run_text)
        ):
            _append_inline_text(last_nested_emphasis[1], run_text)
            last_nested_emphasis = None
            continue
        if len(codes) == 1:
            _append_emphasis(parent, codes[0], run_text)
            last_nested_emphasis = None
        elif codes:
            outer = _append_nested_emphasis(parent, codes, run_text)
            last_nested_emphasis = (tuple(codes), outer)
        else:
            _append_inline_text(parent, run_text)
            last_nested_emphasis = None


def _inline_runs_for_range(
    text: str,
    runs: list[InlineRun] | None,
    start: int,
    end: int,
) -> list[InlineRun]:
    if not runs or start >= end:
        return []
    source = "".join(str(_run_value(run, "text", "")) for run in runs)
    if source != text:
        return []
    selected: list[InlineRun] = []
    position = 0
    for run in runs:
        run_text = str(_run_value(run, "text", ""))
        run_end = position + len(run_text)
        left = max(start, position)
        right = min(end, run_end)
        if left < right:
            selected.append(InlineRun(
                text=run_text[left - position:right - position],
                bold=bool(_run_value(run, "bold")),
                italic=bool(_run_value(run, "italic")),
                underline=bool(_run_value(run, "underline")),
                overline=bool(_run_value(run, "overline")),
                strikethrough=bool(_run_value(run, "strikethrough")),
            ))
        position = run_end
        if position >= end:
            break
    return selected


def _emit_reference(
    parent: etree._Element,
    ref: Mapping[str, object],
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> bool:
    kind = ref.get("kind")
    if kind == "internal":
        target = _resolve_reference(reference_index, ref, current_dm_id)
        if target is None:
            parent.append(_comment(
                f" reference non resolue : {ref.get('text', '')} "
            ))
            return False
        if target.dm_id and target.dm_id != current_dm_id:
            if not target.dmc:
                parent.append(_comment(
                    f" reference inter-DM sans DMC : {ref.get('text', '')} "
                ))
                return False
            dm_ref = etree.SubElement(
                parent,
                "dmRef",
                referredFragment=target.target_id,
            )
            ident = etree.SubElement(dm_ref, "dmRefIdent")
            etree.SubElement(ident, "dmCode", **_dm_code({"dmc": target.dmc}))
            dm_ref.append(_comment(
                f" cible {ref.get('text', '')} dans le DM {target.dmc} "
            ))
            dm_ref.tail = xml_text(str(ref.get("text") or ""))
            return True
        element = etree.SubElement(
            parent,
            "internalRef",
            internalRefId=target.target_id,
            internalRefTargetType=target.target_type,
        )
        element.text = xml_text(str(ref.get("text") or ""))
        return True
    if kind == "uri":
        uri = xml_text(str(ref.get("target") or ""))
        element = etree.SubElement(parent, "externalPubRef")
        element.set(f"{{{_XLINK_NS}}}href", uri)
        element.text = uri
        return True
    parent.append(_comment(f" reference externe non resolue : {ref.get('text', '')} "))
    return False


def _inline_content_with_refs(
    parent: etree._Element,
    text: str,
    runs: list[InlineRun] | None,
    refs: list[dict] | None,
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> None:
    if not refs:
        _inline_content(parent, text, runs)
        return
    if not len(parent) and parent.text is None:
        parent.text = ""
    folded = text.casefold()
    spans: list[tuple[int, int, dict]] = []
    for ref in refs:
        ref_text = str(ref.get("text") or "")
        if not ref_text:
            continue
        start = folded.find(ref_text.casefold())
        if start >= 0:
            spans.append((start, start + len(ref_text), ref))
    spans.sort(key=lambda item: (item[0], item[1]))
    cursor = 0
    for start, end, ref in spans:
        if start < cursor:
            continue
        segment = text[cursor:start]
        _inline_content(
            parent,
            segment,
            _inline_runs_for_range(text, runs, cursor, start),
        )
        if not _emit_reference(
            parent,
            ref,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        ):
            _inline_content(
                parent,
                text[start:end],
                _inline_runs_for_range(text, runs, start, end),
            )
        cursor = end
    _inline_content(
        parent,
        text[cursor:],
        _inline_runs_for_range(text, runs, cursor, len(text)),
    )


def _para(
    parent: etree._Element,
    text: str,
    runs: list[InlineRun] | None = None,
    refs: list[dict] | None = None,
    *,
    reference_index: ReferenceIndex | None = None,
    current_dm_id: str = "",
) -> etree._Element:
    el = etree.SubElement(parent, "para")
    _inline_content_with_refs(
        el,
        text,
        runs,
        refs,
        reference_index=reference_index or {},
        current_dm_id=current_dm_id,
    )
    return el


def _emit_row(parent: etree._Element, cells: list[str]) -> None:
    row_el = etree.SubElement(parent, "row")
    for cell in cells:
        entry = etree.SubElement(row_el, "entry")
        _para(entry, cell)


def _emit_table(parent: etree._Element, node: IRNode, table_number: int) -> None:
    """Modele CALS S1000D : table > (title?) > tgroup > colspec* > thead? > tbody.

    Une ligne d'entete detectee (`table_header`) devient un vrai `<thead>` ; les
    colonnes sont declarees en `<colspec>` (structure attendue par les outils
    S1000D), le reste va dans `<tbody>`."""
    rows = node.table_rows or []
    header = node.table_header
    body_rows = rows
    if header and rows and rows[0] == header:
        body_rows = rows[1:]          # evite de repeter l'entete dans le corps
    ncols = max([len(r) for r in rows] + ([len(header)] if header else []), default=1)
    table = etree.SubElement(parent, "table", id=f"tab-{table_number:04d}")
    if node.text:
        etree.SubElement(table, "title").text = clean_title(node.text)
    tgroup = etree.SubElement(table, "tgroup", cols=str(ncols))
    for c in range(1, ncols + 1):
        etree.SubElement(tgroup, "colspec", colname=f"c{c}")
    if header:
        thead = etree.SubElement(tgroup, "thead")
        _emit_row(thead, header)
    tbody = etree.SubElement(tgroup, "tbody")
    for row in body_rows:
        _emit_row(tbody, row)


def _emit_figure(parent: etree._Element, node: IRNode, figure_number: int) -> None:
    fig = etree.SubElement(parent, "figure", id=f"fig-{figure_number:04d}")
    title = etree.SubElement(fig, "title")
    title.text = clean_figure_title(node.text) or "A REMPLACER"
    if _figure_icns(node):
        # ICN reelle : illustration extraite et enregistree (nom de fichier).
        for icn in _figure_icns(node):
            etree.SubElement(fig, "graphic", infoEntityIdent=_graphic_ident(icn))
    else:
        fig.append(_comment("A REMPLACER: reference ICN de l'illustration."))
        etree.SubElement(fig, "graphic", infoEntityIdent="ICN-ZZZ-00000")


def _emit_admonition(
    parent: etree._Element,
    node: IRNode,
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> None:
    # Fallback si la resolution n'a pas tourne (candidats vides) : sans lui,
    # l'acces `candidates[0]` levait une IndexError -> 500 "Unexpected server error".
    element = _top_element(node, node.admonition or "note")
    el = etree.SubElement(parent, element)
    child = "notePara" if node.admonition == "note" else "warningAndCautionPara"
    para = etree.SubElement(el, child)
    _inline_content_with_refs(
        para,
        node.text,
        node.inline_runs,
        node.refs,
        reference_index=reference_index,
        current_dm_id=current_dm_id,
    )
    if node.admonition == "note":
        for child in node.children:
            if child.kind == "item-sequence" and child.form == "ordered" and child.children:
                _emit_attention_sequential_list(
                    el,
                    child,
                    reference_index=reference_index,
                    current_dm_id=current_dm_id,
                )


def _emit_list(
    parent: etree._Element,
    node: IRNode,
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> None:
    top = _top_element(node, "randomList")
    if top == "proceduralStep":
        # En procedure, chaque item devient une etape independante.
        for item in node.children:
            step = etree.SubElement(parent, "proceduralStep")
            _para(
                step,
                item.text,
                item.inline_runs,
                item.refs,
                reference_index=reference_index,
                current_dm_id=current_dm_id,
            )
        return
    list_el = etree.SubElement(parent, top)
    for item in node.children:
        li = etree.SubElement(list_el, "listItem")
        item_para = _para(
            li,
            item.text,
            item.inline_runs,
            item.refs,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
        for child in item.children:
            if child.kind == "item-sequence":
                _emit_list(
                    item_para,
                    child,
                    reference_index=reference_index,
                    current_dm_id=current_dm_id,
                )


def _emit_attention_sequential_list(
    parent: etree._Element,
    node: IRNode,
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> None:
    sequence = etree.SubElement(parent, "attentionSequentialList")
    for item in node.children:
        list_item = etree.SubElement(sequence, "attentionSequentialListItem")
        item_para = etree.SubElement(list_item, "attentionListItemPara")
        _inline_content_with_refs(
            item_para,
            item.text,
            item.inline_runs,
            item.refs,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )


def _emit_no_req_cond_group(parent: etree._Element) -> None:
    group = etree.SubElement(parent, "reqCondGroup")
    etree.SubElement(group, "noConds")


def _normalized_requirement_heading(value: str) -> str:
    value = clean_title(value or "")
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", ascii_value).strip()


def _procedure_requirement_category(node: IRNode) -> str | None:
    if node.kind != "section":
        return None
    heading = _normalized_requirement_heading(node.text)
    for category, pattern in _PROCEDURE_REQUIREMENT_HEADINGS.items():
        if pattern.search(heading):
            return category
    return None


def _is_preliminary_container(node: IRNode) -> bool:
    return _normalized_requirement_heading(node.text) in _PRELIMINARY_CONTAINER_TITLES


def _requirement_texts(sections: Sequence[IRNode]) -> list[str]:
    texts: list[str] = []
    for section in sections:
        for node in section.walk()[1:]:
            if node.kind in {"paragraph", "item"} and node.text.strip():
                texts.append(node.text.strip())
    return texts


def _explicitly_no_requirement(text: str) -> bool:
    return bool(_NO_REQUIREMENT_RE.match(_normalized_requirement_heading(text)))


def _is_classified_safety_section(section: IRNode) -> bool:
    content = [
        node for node in section.walk()[1:]
        if node.kind in {"paragraph", "item", "admonition", "figure", "table"}
        and not (node.kind == "figure" and node.is_pictogram)
    ]
    if not content:
        return True
    return all(node.kind in {"paragraph", "item", "admonition"} for node in content)


def _partition_preliminary_sections(
    children: Sequence[IRNode],
) -> tuple[list[IRNode], dict[str, list[IRNode]]]:
    main_children: list[IRNode] = []
    requirements: dict[str, list[IRNode]] = {}

    for child in children:
        category = _procedure_requirement_category(child)
        if category == "safety" and not _is_classified_safety_section(child):
            category = None
        if category:
            requirements.setdefault(category, []).append(child)
            continue
        if _is_preliminary_container(child):
            retained, nested = _partition_preliminary_sections(child.children)
            for nested_category, sections in nested.items():
                requirements.setdefault(nested_category, []).extend(sections)
            if retained:
                main_children.append(replace(child, children=retained))
            elif not nested:
                main_children.append(child)
            continue
        main_children.append(child)

    return main_children, requirements


def _emit_condition_requirements(
    parent: etree._Element,
    sections: Sequence[IRNode],
) -> None:
    group = etree.SubElement(parent, "reqCondGroup")
    texts = _requirement_texts(sections)
    conditions = [text for text in texts if not _explicitly_no_requirement(text)]
    if not conditions:
        etree.SubElement(group, "noConds")
        return
    for text in conditions:
        no_ref = etree.SubElement(group, "reqCondNoRef")
        condition = etree.SubElement(no_ref, "reqCond")
        condition.text = xml_text(text)


def _emit_personnel_requirements(
    parent: etree._Element,
    sections: Sequence[IRNode],
) -> None:
    texts = [
        text for text in _requirement_texts(sections)
        if not _explicitly_no_requirement(text)
    ]
    if not texts:
        return

    required_persons = etree.SubElement(parent, "reqPersons")
    for text in texts:
        personnel = etree.SubElement(required_persons, "personnel")
        trade = etree.SubElement(personnel, "trade")
        trade.text = xml_text(text)


def _emit_material_requirements(
    parent: etree._Element,
    *,
    container_tag: str,
    no_tag: str,
    group_tag: str,
    item_tag: str,
    sections: Sequence[IRNode],
) -> None:
    container = etree.SubElement(parent, container_tag)
    texts = _requirement_texts(sections)
    materials = [text for text in texts if not _explicitly_no_requirement(text)]
    if not materials:
        etree.SubElement(container, no_tag)
        return

    group = etree.SubElement(container, group_tag)
    for text in materials:
        item = etree.SubElement(group, item_tag)
        name = etree.SubElement(item, "name")
        name.text = xml_text(text)
        item.append(_comment("A REMPLACER: code fabricant, quantite et unite de mesure."))
        ident_number = etree.SubElement(item, "identNumber")
        manufacturer = etree.SubElement(ident_number, "manufacturerCode")
        manufacturer.text = "A REMPLACER"
        quantity = etree.SubElement(item, "reqQuantity", unitOfMeasure="A REMPLACER")
        quantity.text = "A REMPLACER"


def _emit_safety_requirements(
    parent: etree._Element,
    sections: Sequence[IRNode],
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> None:
    requirement = etree.SubElement(parent, "reqSafety")
    texts = _requirement_texts(sections)
    admonitions = [
        node
        for section in sections
        for node in section.walk()[1:]
        if node.kind == "admonition"
    ]
    if not sections or (not texts and not admonitions):
        etree.SubElement(requirement, "noSafety")
        return
    if texts and all(_explicitly_no_requirement(text) for text in texts) and not admonitions:
        etree.SubElement(requirement, "noSafety")
        return

    safety = etree.SubElement(requirement, "safetyRqmts")
    for node in _ordered_children(admonitions):
        _emit_admonition(
            safety,
            node,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
    for section in sections:
        for node in section.walk()[1:]:
            if node.kind not in {"paragraph", "item"} or _explicitly_no_requirement(node.text):
                continue
            note = etree.SubElement(safety, "note")
            note_para = etree.SubElement(note, "notePara")
            note_para.text = xml_text(node.text)


def _emit_preliminary_requirements(
    parent: etree._Element,
    requirements: Mapping[str, Sequence[IRNode]],
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> None:
    preliminary = etree.SubElement(parent, "preliminaryRqmts")
    production = etree.SubElement(preliminary, "productionMaintData")
    threshold = etree.SubElement(
        production,
        "thresholdInterval",
        thresholdUnitOfMeasure="th02",
    )
    threshold.text = "1"
    etree.SubElement(
        production,
        "taskDuration",
        closeupDuration="0",
        procedureDuration="4",
        startupDuration="0",
        unitOfMeasure="h",
    )
    _emit_condition_requirements(preliminary, requirements.get("conditions", []))
    _emit_personnel_requirements(preliminary, requirements.get("personnel", []))
    _emit_material_requirements(
        preliminary,
        container_tag="reqSupportEquips",
        no_tag="noSupportEquips",
        group_tag="supportEquipDescrGroup",
        item_tag="supportEquipDescr",
        sections=requirements.get("support", []),
    )
    _emit_material_requirements(
        preliminary,
        container_tag="reqSupplies",
        no_tag="noSupplies",
        group_tag="supplyDescrGroup",
        item_tag="supplyDescr",
        sections=requirements.get("supplies", []),
    )
    _emit_material_requirements(
        preliminary,
        container_tag="reqSpares",
        no_tag="noSpares",
        group_tag="spareDescrGroup",
        item_tag="spareDescr",
        sections=requirements.get("spares", []),
    )
    _emit_safety_requirements(
        preliminary,
        requirements.get("safety", []),
        reference_index=reference_index,
        current_dm_id=current_dm_id,
    )


def _is_descriptive_list(node: IRNode) -> bool:
    return _top_element(node, "randomList") in {
        "randomList", "sequentialList", "definitionList",
    }


def _ordered_children(children: list[IRNode]) -> list[IRNode]:
    priority = {
        "warning": 0,
        "caution": 1,
    }
    ordered = sorted(
        enumerate(children),
        key=lambda item: (priority.get(item[1].admonition or "", 2), item[0]),
    )
    return [child for _index, child in ordered]


def _emit_children(
    parent: etree._Element,
    children: list[IRNode],
    counters: dict[str, int],
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> None:
    last_para: etree._Element | None = None
    for child in _ordered_children(children):
        if child.zone in _LAYOUT_NOISE_ZONES:
            continue
        if child.kind == "item-sequence" and _is_descriptive_list(child):
            list_parent = last_para
            if list_parent is None:
                list_parent = etree.SubElement(parent, "para")
            _emit_list(
                list_parent,
                child,
                reference_index=reference_index,
                current_dm_id=current_dm_id,
            )
            continue
        emitted = _emit_node(
            parent,
            child,
            counters,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
        last_para = emitted if emitted is not None and emitted.tag == "para" else None


def _has_figure_after_procedural_step(children: Sequence[IRNode]) -> bool:
    has_step = False
    for child in children:
        if (
            child.kind == "table"
            or (child.kind == "figure" and not child.is_pictogram)
        ) and has_step:
            return True
        if child.kind == "section" and _top_element(child, "levelledPara") == "proceduralStep":
            has_step = True
        elif child.kind == "paragraph" and _top_element(child, "para") == "proceduralStep":
            has_step = True
        elif child.kind == "item-sequence" and _top_element(child, "randomList") == "proceduralStep":
            has_step = True
    return False


def _is_numbered_procedure_group(node: IRNode) -> bool:
    if node.kind != "section" or node.text or node.context != "procedural":
        return False
    if len(node.children) != 2:
        return False
    introduction, sequence = node.children
    return (
        introduction.kind == "paragraph"
        and introduction.text.rstrip().endswith(":")
        and sequence.kind == "item-sequence"
        and sequence.form == "ordered"
        and bool(sequence.children)
    )


def _has_numbered_procedure_group(children: Sequence[IRNode]) -> bool:
    return any(_is_numbered_procedure_group(child) for child in children)


def _emit_numbered_procedure_group(
    parent: etree._Element,
    node: IRNode,
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> etree._Element | None:
    introduction, sequence = node.children
    _para(
        parent,
        introduction.text,
        introduction.inline_runs,
        introduction.refs,
        reference_index=reference_index,
        current_dm_id=current_dm_id,
    )
    last_step: etree._Element | None = None
    for item in sequence.children:
        step = etree.SubElement(parent, "proceduralStep")
        _para(
            step,
            item.text,
            item.inline_runs,
            item.refs,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
        last_step = step
    return last_step


def _emit_procedural_step_children(
    parent: etree._Element,
    children: Sequence[IRNode],
    counters: dict[str, int],
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> None:
    current_step: etree._Element | None = None
    for child in _ordered_children(list(children)):
        if child.zone in _LAYOUT_NOISE_ZONES:
            continue
        if _is_numbered_procedure_group(child):
            current_step = _emit_numbered_procedure_group(
                parent,
                child,
                reference_index=reference_index,
                current_dm_id=current_dm_id,
            )
            continue
        if child.kind in {"figure", "table"} and current_step is not None:
            _emit_node(
                current_step,
                child,
                counters,
                reference_index=reference_index,
                current_dm_id=current_dm_id,
            )
            continue
        if child.kind == "paragraph" and current_step is not None:
            _para(
                current_step,
                child.text,
                child.inline_runs,
                child.refs,
                reference_index=reference_index,
                current_dm_id=current_dm_id,
            )
            continue

        previous_count = len(parent)
        _emit_node(
            parent,
            child,
            counters,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
        new_steps = [
            element for element in list(parent)[previous_count:]
            if element.tag == "proceduralStep"
        ]
        if new_steps:
            current_step = new_steps[-1]


def _emit_node(
    parent: etree._Element,
    node: IRNode,
    counters: dict[str, int],
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> etree._Element | None:
    if node.zone in _LAYOUT_NOISE_ZONES:
        return None
    if node.kind == "figure" and node.is_pictogram:
        return None
    alt = _alt_comment(node)
    if alt:
        parent.append(etree.Comment(alt))

    if node.kind == "admonition":
        _emit_admonition(
            parent,
            node,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
        return None
    elif node.kind == "figure":
        counters["figure"] += 1
        _emit_figure(parent, node, counters["figure"])
        return None
    elif node.kind == "table":
        counters["table"] += 1
        _emit_table(parent, node, counters["table"])
        return None
    elif node.kind == "item-sequence":
        _emit_list(
            parent,
            node,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
        return None
    elif node.kind == "paragraph":
        top = _top_element(node, "para")
        if top == "proceduralStep":
            step = etree.SubElement(parent, "proceduralStep")
            _para(
                step,
                node.text,
                node.inline_runs,
                node.refs,
                reference_index=reference_index,
                current_dm_id=current_dm_id,
            )
            return None
        else:
            para = _para(
                parent,
                node.text,
                node.inline_runs,
                node.refs,
                reference_index=reference_index,
                current_dm_id=current_dm_id,
            )
            return para
    elif node.kind == "section":
        if parent.tag == "mainProcedure" and _is_numbered_procedure_group(node):
            step = etree.SubElement(parent, "proceduralStep")
            _emit_numbered_procedure_group(step, node, reference_index=reference_index,
                                           current_dm_id=current_dm_id)
            return None

        if parent.tag == "proceduralStep" and _is_numbered_procedure_group(node):
            _emit_numbered_procedure_group(
                parent,
                node,
                reference_index=reference_index,
                current_dm_id=current_dm_id,
            )
            return None

        if parent.tag in {"mainProcedure", "proceduralStep"} and (
            _has_figure_after_procedural_step(node.children)
            or _has_numbered_procedure_group(node.children)
        ):
            counters["section"] += 1
            procedure_step = etree.SubElement(
                parent,
                "proceduralStep",
                id=f"par-{counters['section']:04d}",
            )
            if node.text:
                title = etree.SubElement(procedure_step, "title")
                title.text = clean_title(node.text)
            _emit_procedural_step_children(
                procedure_step,
                node.children,
                counters,
                reference_index=reference_index,
                current_dm_id=current_dm_id,
            )
            return None

        top = "proceduralStep" if parent.tag == "mainProcedure" else _top_element(node, "levelledPara")
        counters["section"] += 1
        sect = etree.SubElement(parent, top, id=f"par-{counters['section']:04d}")
        if node.text:
            title = etree.SubElement(sect, "title")
            title.text = clean_title(node.text)
        _emit_children(
            sect,
            node.children,
            counters,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
        return None
    return None


def _build_content(
    root: IRNode,
    dm_type: str,
    counters: dict[str, int],
    *,
    reference_index: ReferenceIndex,
    current_dm_id: str,
) -> etree._Element:
    content = etree.Element("content")
    if dm_type == "procedural":
        proc = etree.SubElement(content, "procedure")
        main_children, requirements = _partition_preliminary_sections(root.children)
        _emit_preliminary_requirements(
            proc,
            requirements,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
        main = etree.SubElement(proc, "mainProcedure")
        _emit_children(
            main,
            main_children,
            counters,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
        if not any(isinstance(child.tag, str) for child in main):
            counters["section"] += 1
            placeholder_step = etree.SubElement(
                main,
                "proceduralStep",
                id=f"par-{counters['section']:04d}",
            )
            placeholder_step.append(_comment(
                "A REMPLACER: aucune etape de procedure n'a ete detectee dans la source."
            ))
            etree.SubElement(placeholder_step, "title").text = "Etape a renseigner"
            etree.SubElement(placeholder_step, "para").text = (
                "Etape de procedure a completer a partir de la source."
            )
        close = etree.SubElement(proc, "closeRqmts")
        _emit_no_req_cond_group(close)
    elif dm_type == "ipd":
        etree.SubElement(content, "illustratedPartsCatalog")
    else:
        desc = etree.SubElement(content, "description")
        _emit_children(
            desc,
            root.children,
            counters,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
    return content


def _indent_element_only(element: etree._Element, level: int = 0) -> None:
    children = list(element)
    if not children:
        return
    mixed_content = (
        element.tag in _MIXED_CONTENT_TAGS
        or bool(element.text and element.text.strip())
        or any(child.tail and child.tail.strip() for child in children)
    )
    if mixed_content:
        return
    if not (element.text and element.text.strip()):
        element.text = "\n" + "  " * (level + 1)
    for child in children:
        if isinstance(child.tag, str):
            _indent_element_only(child, level + 1)
        if not (child.tail and child.tail.strip()):
            child.tail = "\n" + "  " * level


def serialize(
    root: IRNode,
    *,
    issue: str,
    dm_type: str,
    title: str = "",
    dm_metadata: Mapping[str, object] | None = None,
    missing_fields: Sequence[str] = (),
    header_template: Mapping[str, object] | None = None,
    reference_index: ReferenceIndex | None = None,
    reference_dm_id: str = "",
    created_at: datetime | None = None,
    diagnostics: SerializationDiagnostics | None = None,
) -> str:
    """Construit un squelette XML S1000D contraint par le XSD local (UTF-8 indente)."""
    if issue not in {"4.1", "4.2"}:
        raise ValueError(f"Generation XSD non disponible pour l'Issue {issue}.")
    normalized_type = _normalize_dm_type(dm_type)
    if reference_index is None:
        reference_metadata = dict(dm_metadata or {})
        reference_metadata.update({"dm_type": normalized_type, "issue": issue})
        reference_index = build_reference_index(
            [(reference_dm_id, root, reference_metadata)],
        )
    counters = {
        "figure": 0,
        "table": 0,
        "section": 0,
    }
    dmodule = etree.Element("dmodule", nsmap={
        "xsi": _XSI_NS,
        "xlink": _XLINK_NS,
        "rdf": _RDF_NS,
        "dc": _DC_NS,
    })
    dmodule.addprevious(etree.Comment(_BANNER))
    dmodule.set(f"{{{_XSI_NS}}}noNamespaceSchemaLocation", _schema_location(issue, normalized_type))
    _emit_header(
        dmodule,
        issue=issue,
        dm_type=dm_type,
        title=title,
        dm_metadata=dm_metadata,
        header_template=header_template,
        created_at=created_at,
    )

    dmodule.append(_build_content(
        root,
        normalized_type,
        counters,
        reference_index=reference_index,
        current_dm_id=reference_dm_id,
    ))
    xsd_report: ConstraintReport = load_xsd_model(issue, normalized_type).constrain(dmodule)
    normalize_dm_ids(dmodule)
    if normalized_type == "ipd" and _content_nodes(root):
        xsd_report.violations.append({
            "severity": "error",
            "rule": "XSD",
            "message": (
                "Aucun mapping IPD ne permet de representer les noeuds source "
                "comme des references de pieces; ils n'ont pas ete emis."
            ),
            "path": "/dmodule/content/illustratedPartsCatalog",
        })
    missing = list(missing_fields)
    missing.extend(_missing_dm_code_fields(dm_metadata))
    missing.extend(_header_provisional_fields(header_template, dm_metadata))
    missing.extend(xsd_report.provisional_fields)
    missing = _collect_missing_data_fields(dmodule, missing)
    if missing:
        dmodule.append(_comment(
            _MISSING_DATA_COMMENT_PREFIX + " " + "; ".join(missing)
        ))
    if diagnostics is not None:
        diagnostics.xsd_violations.extend(xsd_report.violations)
        diagnostics.provisional_fields.extend(xsd_report.provisional_fields)

    _indent_element_only(dmodule)
    tree = dmodule.getroottree()
    return etree.tostring(
        tree, pretty_print=True, xml_declaration=True, encoding="UTF-8",
        doctype=_doctype(root, dmodule),
    ).decode("utf-8")
