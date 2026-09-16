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

from collections.abc import Mapping
from datetime import UTC, datetime
import re

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


def xml_text(value: str | None) -> str:
    """Texte utilisable comme contenu XML (caracteres de controle retires)."""
    return _INVALID_XML_CHARS.sub("", value or "")


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
    for node in root.walk():
        if node.kind != "figure":
            continue
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
    declarations.extend((
        '<!ENTITY % ISOEntities PUBLIC '
        '"ISO 8879-1986//ENTITIES ISO Character Entities 20030531//EN//XML" '
        '"ent/ISOEntities">',
        "%ISOEntities;",
    ))
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


def _emit_refs(parent: etree._Element, node: IRNode) -> None:
    """Emet les renvois detectes (best-effort) : `internalRef` pour un renvoi
    interne (figure/table/section), `externalPubRef` sinon, commentaire pour une
    URL. La cible S1000D (DMC/xref) reste a completer (marquee TODO)."""
    for ref in node.refs or []:
        kind = ref.get("kind")
        if kind == "internal":
            el = etree.SubElement(
                parent, "internalRef",
                internalRefTargetType=xml_text(ref.get("target_kind", "section")),
            )
            el.set("internalRefId", f"TODO-{xml_text(ref.get('target', ''))}")
            el.append(_comment(f" renvoi detecte : {ref.get('text', '')} "))
        elif kind == "uri":
            parent.append(_comment(f" lien externe (a mapper) : {ref.get('target', '')} "))
        else:
            etree.SubElement(parent, "externalPubRef").append(
                _comment(f" TODO: publication externe : {ref.get('text', '')} ")
            )


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


def _inline_content(
    parent: etree._Element,
    text: str,
    runs: list[InlineRun] | None = None,
) -> None:
    usable_runs = runs or []
    if usable_runs and "".join(str(_run_value(run, "text", "")) for run in usable_runs) != text:
        usable_runs = []
    if not usable_runs:
        _append_inline_text(parent, text)
        return
    for run in usable_runs:
        run_text = str(_run_value(run, "text", ""))
        code = _run_emphasis_code(run)
        if code:
            emphasis = etree.SubElement(parent, "emphasis", emphasisType=code)
            emphasis.text = xml_text(run_text)
        else:
            _append_inline_text(parent, run_text)


def _para(parent: etree._Element, text: str, runs: list[InlineRun] | None = None) -> None:
    el = etree.SubElement(parent, "para")
    _inline_content(el, text, runs)


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


def _emit_admonition(parent: etree._Element, node: IRNode) -> None:
    # Fallback si la resolution n'a pas tourne (candidats vides) : sans lui,
    # l'acces `candidates[0]` levait une IndexError -> 500 "Unexpected server error".
    element = _top_element(node, node.admonition or "note")
    el = etree.SubElement(parent, element)
    child = "notePara" if node.admonition == "note" else "warningAndCautionPara"
    para = etree.SubElement(el, child)
    _inline_content(para, node.text, node.inline_runs)


def _emit_list(parent: etree._Element, node: IRNode) -> None:
    top = _top_element(node, "randomList")
    if top == "proceduralStep":
        # En procedure, chaque item devient une etape independante.
        for item in node.children:
            step = etree.SubElement(parent, "proceduralStep")
            _para(step, item.text, item.inline_runs)
        return
    list_el = etree.SubElement(parent, top)
    for item in node.children:
        li = etree.SubElement(list_el, "listItem")
        _para(li, item.text, item.inline_runs)
        _emit_refs(li, item)


def _emit_node(
    parent: etree._Element,
    node: IRNode,
    counters: dict[str, int],
) -> None:
    alt = _alt_comment(node)
    if alt:
        parent.append(etree.Comment(alt))

    if node.kind == "admonition":
        _emit_admonition(parent, node)
        _emit_refs(parent, node)
    elif node.kind == "figure":
        counters["figure"] += 1
        _emit_figure(parent, node, counters["figure"])
        _emit_refs(parent, node)
    elif node.kind == "table":
        counters["table"] += 1
        _emit_table(parent, node, counters["table"])
    elif node.kind == "item-sequence":
        _emit_list(parent, node)
    elif node.kind == "paragraph":
        top = _top_element(node, "para")
        if top == "proceduralStep":
            step = etree.SubElement(parent, "proceduralStep")
            _para(step, node.text, node.inline_runs)
            _emit_refs(step, node)
        else:
            _para(parent, node.text, node.inline_runs)
            _emit_refs(parent, node)
    elif node.kind == "section":
        top = _top_element(node, "levelledPara")
        sect = etree.SubElement(parent, top)
        if node.text:
            title = etree.SubElement(sect, "title")  # optionnel mais conventionnel
            title.text = clean_title(node.text)
        for child in node.children:
            _emit_node(sect, child, counters)


def _build_content(
    root: IRNode,
    dm_type: str,
    counters: dict[str, int],
) -> etree._Element:
    content = etree.Element("content")
    if dm_type == "procedural":
        proc = etree.SubElement(content, "procedure")
        proc.append(etree.Comment(" TODO: preliminaryRqmts (outillage, consommables, conditions) "))
        etree.SubElement(proc, "preliminaryRqmts")
        main = etree.SubElement(proc, "mainProcedure")
        for child in root.children:
            _emit_node(main, child, counters)
        etree.SubElement(proc, "closeRqmts")
    else:
        desc = etree.SubElement(content, "description")
        if dm_type == "ipd":
            desc.append(etree.Comment(
                " TODO: catalogue de pieces (IPD/IPC) - structurer en catalogSeqNumber/itemSeqNumber "
            ))
        for child in root.children:
            _emit_node(desc, child, counters)
    return content


def serialize(
    root: IRNode,
    *,
    issue: str,
    dm_type: str,
    title: str = "",
    figure_offset: int = 0,
    table_offset: int = 0,
    dm_metadata: Mapping[str, object] | None = None,
    header_template: Mapping[str, object] | None = None,
    created_at: datetime | None = None,
) -> str:
    """Construit le squelette XML S1000D complet (string UTF-8 indentee)."""
    counters = {"figure": figure_offset, "table": table_offset}
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

    dmodule.append(_build_content(root, dm_type, counters))

    tree = dmodule.getroottree()
    return etree.tostring(
        tree, pretty_print=True, xml_declaration=True, encoding="UTF-8",
        doctype=_doctype(root),
    ).decode("utf-8")
