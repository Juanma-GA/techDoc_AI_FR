"""Serialiseur : IR resolu -> squelette XML S1000D (lxml).

ATTENTION (ecart assume) : la sortie est un SQUELETTE STRUCTUREL best-effort,
PAS un Data Module valide. Les metadonnees non recuperables d'un PDF/Word
(DMC, SNS, applicabilite, securite, ICN des graphics) sont des placeholders
marques `<!-- TODO ... -->` a completer par un humain.

Noms d'elements conformes Issue 4.1 / 4.2 / 5.0 (stables entre les trois) :
- bloc d'identification : `identAndStatusSection` (`dmAddress` + `dmStatus`,
  le `brexDmRef` vit dans `dmStatus`) ;
- listes : `randomList`/`sequentialList` > `listItem` > `para` ;
- procedure : `procedure` > `mainProcedure` > `proceduralStep` > `para` ;
- admonitions : `warning`/`caution` > `warningAndCautionPara`, `note` > `notePara` ;
- figure : `figure` > `title` + `graphic[@infoEntityIdent]` (PAS `boardno`, legacy 2.x) ;
- tableaux : modele CALS `table` > `tgroup` > `tbody` > `row` > `entry` > `para`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
import re
import unicodedata

from lxml import etree

from app.core.dm_header import DEFAULT_HEADER_TEMPLATE
from app.core.ir import IRNode, InlineRun
from app.core.pmc import parse_dmc
from app.core.s1000d_codes import emphasis_code_for_style, get_code

_BANNER = (
    " Squelette structurel best-effort genere par s1000d extractor. "
    "NON valide comme Data Module : DMC / SNS / applicabilite / securite / ICN "
    "a completer manuellement (voir les commentaires TODO). "
)

# Caracteres de controle interdits en XML 1.0 (le texte d'un PDF en contient
# souvent : form feed, NUL...). lxml leve une ValueError -> 500 cote API. On les
# retire au seuil de la serialisation, une fois pour toutes.
_INVALID_XML_CHARS = re.compile(r"[^\u0009\u000A\u000D\u0020-\uD7FF\uE000-\uFFFD]")
# Nom d'element XML valide (les candidats viennent d'un override humain / LLM).
_NCNAME = re.compile(r"^[A-Za-z_][\w.\-]*$")
_GRAPHIC_EXTENSION = re.compile(r"\.(?:jpe?g|png)$", re.IGNORECASE)
_GRAPHIC_NOTATION = {".jpg": "jpg", ".jpeg": "jpg", ".png": "png"}
_FIGURE_TITLE_PREFIX = re.compile(
    r"^\s*(?:figure|fig\.?|illustration)\s+\d+(?:[.\-]\d+)*"
    r"(?:\s*[:.\-\u2013\u2014]\s*|\s+)",
    re.IGNORECASE,
)
_NUMBERED_TITLE_PREFIX = re.compile(
    r"^\s*\d+(?:\.\d+)*(?:\s*[.)\-\u2013\u2014:]\s*|\s+)",
)
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
_DM_CODE_DEFAULTS = {
    "assyCode": "00",
    "disassyCode": "00",
    "disassyCodeVariant": "A",
    "infoCode": "040",
    "infoCodeVariant": "A",
    "itemLocationCode": "D",
    "modelIdentCode": "TODO",
    "subSubSystemCode": "0",
    "subSystemCode": "0",
    "systemCode": "00",
    "systemDiffCode": "A",
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
            if child.zone in _LAYOUT_NOISE_ZONES:
                continue
            nodes.append(child)
            walk(child)

    walk(root)
    return nodes


def content_node_count(root: IRNode, kind: str) -> int:
    return sum(node.kind == kind for node in _content_nodes(root))


def build_reference_index(
    documents: Sequence[tuple[str, IRNode, Mapping[str, object] | None]],
    *,
    figure_offset: int = 0,
    table_offset: int = 0,
    section_offset: int = 0,
) -> ReferenceIndex:
    """Indexe les cibles visibles avec les IDs emis dans les DM.

    `documents` respecte l'ordre de generation : les offsets produits ici
    doivent donc rester synchronises avec ceux passes a `serialize`.
    """
    index: ReferenceIndex = {}
    for dm_id, root, metadata in documents:
        dmc = str((metadata or {}).get("dmc") or "")
        nodes = _content_nodes(root)
        for position, node in enumerate(nodes):
            if node.kind == "section":
                section_offset += 1
                target = ReferenceTarget(
                    kind="section",
                    label="",
                    target_id=f"par-{section_offset:04d}",
                    target_type=_INTERNAL_REF_CODES["section"],
                    dm_id=dm_id,
                    dmc=dmc,
                )
                for label in _labels_for_text("section", node.text):
                    _add_reference_target(index, ReferenceTarget(
                        kind=target.kind, label=label, target_id=target.target_id,
                        target_type=target.target_type, dm_id=target.dm_id, dmc=target.dmc,
                    ))
            elif node.kind == "figure":
                figure_offset += 1
                target_id = f"fig-{figure_offset:04d}"
                for label in _labels_for_text("figure", node.text):
                    _add_reference_target(index, ReferenceTarget(
                        kind="figure", label=label, target_id=target_id,
                        target_type=_INTERNAL_REF_CODES["figure"], dm_id=dm_id, dmc=dmc,
                    ))
            elif node.kind == "table":
                table_offset += 1
                target_id = f"tbl-{table_offset:04d}"
                labels = _labels_for_text("table", node.text)
                if not labels:
                    nearby = nodes[max(0, position - 3):position + 4]
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
                for label in labels:
                    _add_reference_target(index, ReferenceTarget(
                        kind="table", label=label, target_id=target_id,
                        target_type=_INTERNAL_REF_CODES["table"], dm_id=dm_id, dmc=dmc,
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


def _doctype(root: IRNode) -> str:
    """Construit la DTD interne qui declare les fichiers graphiques du DM."""
    declarations: list[str] = []
    declared: set[str] = set()
    placeholder_ident = "ICN-TODO-00000"
    for node in root.walk():
        if node.kind != "figure":
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
    return "<!DOCTYPE dmodule [\n" + "\n".join(declarations) + "\n]>"


def _schema_location(issue: str, dm_type: str) -> str:
    issue_path = xml_text(issue).replace(".", "-")
    schema_name = _SCHEMA_NAMES.get((dm_type or "descriptive").lower(), "descript.xsd")
    return f"http://www.s1000d.org/S1000D_{issue_path}/xml_schema_flat/{schema_name}"


def _dm_code(metadata: Mapping[str, object] | None, dm_type: str) -> dict[str, str]:
    data = metadata or {}
    values = dict(_DM_CODE_DEFAULTS)
    parsed = parse_dmc(str(data.get("dmc") or ""))
    if parsed:
        values.update(parsed)
    for xml_name, field_name in _DM_FIELD_NAMES.items():
        value = data.get(field_name)
        if value:
            values[xml_name] = str(value).strip()
    if not parsed and not data.get("info_code"):
        values["infoCode"] = {"procedural": "520", "ipd": "941"}.get(dm_type, "040")
    return {key: xml_text(value) for key, value in values.items()}


def _text(value: object, fallback: str = "") -> str:
    return xml_text(str(value)) if value is not None else fallback


def _company(parent: etree._Element, name: str, data: Mapping[str, object]) -> None:
    company = etree.SubElement(parent, name, enterpriseCode=_text(data.get("enterpriseCode"), "EX"))
    etree.SubElement(company, "enterpriseName").text = _text(
        data.get("enterpriseName"), "EXAMPLE ORGANIZATION"
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
    etree.SubElement(display, "simplePara").text = _text(template.get("applicability"), "All")

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
    etree.SubElement(dm_ident, "dmCode", **_dm_code(metadata, dm_type))
    language = template.get("language") or {}
    etree.SubElement(dm_ident, "language", countryIsoCode=_text(language.get("countryIsoCode"), "FR"), languageIsoCode=_text(language.get("languageIsoCode"), "fr"))
    etree.SubElement(dm_ident, "issueInfo", inWork="00", issueNumber="001")
    items = etree.SubElement(address, "dmAddressItems")
    now = created_at or datetime.now(UTC)
    etree.SubElement(items, "issueDate", day=f"{now.day:02d}", month=f"{now.month:02d}", year=str(now.year))
    dm_title = etree.SubElement(items, "dmTitle")
    etree.SubElement(dm_title, "techName").text = _text(metadata.get("tech_name"), _text(title, "Data Module"))
    etree.SubElement(dm_title, "infoName").text = _text(metadata.get("info_name"), _text(title, "Data Module"))
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


def _run_emphasis_code(run: InlineRun | dict) -> str | None:
    if not str(_run_value(run, "text", "")).strip():
        return None
    for style in ("bold", "italic", "underline", "overline", "strikethrough"):
        if not bool(_run_value(run, style, False)):
            continue
        code = emphasis_code_for_style(style)
        if code and get_code("emphasisType", code):
            return code
    return None


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
    for run in usable_runs:
        run_text = str(_run_value(run, "text", ""))
        code = _run_emphasis_code(run)
        if code:
            _append_emphasis(parent, code, run_text)
        else:
            _append_inline_text(parent, run_text)


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
            etree.SubElement(ident, "dmCode", **_dm_code({"dmc": target.dmc}, "descriptive"))
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
    table = etree.SubElement(parent, "table", id=f"tbl-{table_number:04d}")
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
    title.text = clean_title(node.text) or "Figure"
    if _figure_icns(node):
        # ICN reelle : illustration extraite et enregistree (nom de fichier).
        for icn in _figure_icns(node):
            etree.SubElement(fig, "graphic", infoEntityIdent=_graphic_ident(icn))
    else:
        fig.append(etree.Comment(" TODO: ICN du graphic a referencer (infoEntityIdent) "))
        etree.SubElement(fig, "graphic", infoEntityIdent="ICN-TODO-00000")


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
        _para(
            li,
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
        ident_number = etree.SubElement(item, "identNumber")
        manufacturer = etree.SubElement(ident_number, "manufacturerCode")
        manufacturer.text = "TODO"
        quantity = etree.SubElement(item, "reqQuantity", unitOfMeasure="TODO")
        quantity.text = "TODO"


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
        if child.kind in {"figure", "table"} and has_step:
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
        close = etree.SubElement(proc, "closeRqmts")
        _emit_no_req_cond_group(close)
    else:
        desc = etree.SubElement(content, "description")
        if dm_type == "ipd":
            desc.append(etree.Comment(
                " TODO: catalogue de pieces (IPD/IPC) - structurer en catalogSeqNumber/itemSeqNumber "
            ))
        _emit_children(
            desc,
            root.children,
            counters,
            reference_index=reference_index,
            current_dm_id=current_dm_id,
        )
    return content


def serialize(
    root: IRNode,
    *,
    issue: str,
    dm_type: str,
    title: str = "",
    figure_offset: int = 0,
    table_offset: int = 0,
    section_offset: int = 0,
    dm_metadata: Mapping[str, object] | None = None,
    header_template: Mapping[str, object] | None = None,
    reference_index: ReferenceIndex | None = None,
    reference_dm_id: str = "",
    created_at: datetime | None = None,
) -> str:
    """Construit le squelette XML S1000D complet (string UTF-8 indentee)."""
    if reference_index is None:
        reference_index = build_reference_index(
            [(reference_dm_id, root, dm_metadata)],
            figure_offset=figure_offset,
            table_offset=table_offset,
            section_offset=section_offset,
        )
    counters = {
        "figure": figure_offset,
        "table": table_offset,
        "section": section_offset,
    }
    dmodule = etree.Element("dmodule", nsmap={
        "xsi": _XSI_NS,
        "xlink": _XLINK_NS,
        "rdf": _RDF_NS,
        "dc": _DC_NS,
    })
    dmodule.addprevious(etree.Comment(_BANNER))
    dmodule.set(f"{{{_XSI_NS}}}noNamespaceSchemaLocation", _schema_location(issue, dm_type))
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
        dm_type,
        counters,
        reference_index=reference_index,
        current_dm_id=reference_dm_id,
    ))

    tree = dmodule.getroottree()
    return etree.tostring(
        tree, pretty_print=True, xml_declaration=True, encoding="UTF-8",
        doctype=_doctype(root),
    ).decode("utf-8")
