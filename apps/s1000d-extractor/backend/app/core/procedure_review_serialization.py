"""Serialize human-selected tags within procedural requirement categories."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Literal

from lxml import etree

from app.core.ir import IRNode
from app.core.procedure_semantics import Resource, resource_rows

_NO_REQUIREMENT_RE = re.compile(
    r"^(?:no\b|none\b|not required\b|not applicable\b|"
    r"aucun(?:e|s|es)?\b|pas de\b|sans\b)"
)
EmitAdmonition = Callable[[etree._Element, IRNode], None]
CommentFactory = Callable[[str], etree._Comment]
TextSanitizer = Callable[[str | None], str]
SafetyTag = Literal["warning", "caution", "note"]
_SAFETY_TAGS: dict[str, SafetyTag] = {
    "warning": "warning",
    "caution": "caution",
    "note": "note",
}


def _explicitly_no_requirement(text: str) -> bool:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()
    return bool(_NO_REQUIREMENT_RE.match(normalized))


def _selected_safety_tag(node: IRNode) -> SafetyTag | None:
    if not node.candidates:
        return None
    return _SAFETY_TAGS.get(node.candidates[0].element)


def emit_condition_requirements(
    parent: etree._Element,
    sections: Sequence[IRNode],
    *,
    xml_text: TextSanitizer,
    reviewed: bool,
) -> None:
    group = etree.SubElement(parent, "reqCondGroup")
    resources = resource_rows(sections)
    conditions = [
        row for row in resources
        if not _explicitly_no_requirement(row.text)
        and (not reviewed or row.target_tag != "noConds")
    ]
    if not conditions:
        etree.SubElement(group, "noConds")
        return
    for row in conditions:
        no_ref = etree.SubElement(group, "reqCondNoRef")
        condition = etree.SubElement(no_ref, "reqCond")
        condition.text = xml_text(row.text)


def _emit_personnel_requirements(
    parent: etree._Element,
    sections: Sequence[IRNode],
    *,
    xml_text: TextSanitizer,
    reviewed: bool,
) -> None:
    people = [
        row for row in resource_rows(sections)
        if not _explicitly_no_requirement(row.text)
    ]
    if not people:
        return

    required_persons = etree.SubElement(parent, "reqPersons")
    for person in people:
        personnel = etree.SubElement(required_persons, "personnel")
        person_text = person.text.strip()
        quantity = person.quantity
        count = re.match(r"^(\d+)\s+(.+)$", person_text)
        if not quantity and count:
            quantity, person_text = count.groups()
        if quantity and re.fullmatch(r"\d+", quantity):
            personnel.set("numRequired", quantity)
        tag = person.target_tag if reviewed else None
        if tag == "personCategory":
            etree.SubElement(
                personnel, "personCategory", personCategoryCode=xml_text(person_text),
            )
        elif tag == "personSkill":
            etree.SubElement(personnel, "personSkill", skillLevelCode=xml_text(person_text))
        else:
            trade = etree.SubElement(personnel, "trade")
            trade.text = xml_text(person_text)


def _emit_material_item(
    parent: etree._Element,
    material: Resource,
    *,
    item_tag: str,
    xml_text: TextSanitizer,
    comment: CommentFactory,
    reviewed: bool,
) -> None:
    item = etree.SubElement(parent, item_tag)
    tag = material.target_tag if reviewed else None
    selected_text = material.text.strip()

    name_value = selected_text if tag == "name" else material.name
    if tag in {"identNumber", "manufacturerCode", "partAndSerialNumber", "partNumber", "reqQuantity"}:
        name_value = "A REMPLACER"
    etree.SubElement(item, "name").text = xml_text(name_value)

    if not all((material.manufacturer, material.quantity, material.unit)):
        item.append(comment("A REMPLACER: champs fabricant, quantite ou unite absents de la source."))

    ident_number = etree.SubElement(item, "identNumber")
    manufacturer_value = material.manufacturer or "A REMPLACER"
    if tag in {"identNumber", "manufacturerCode"}:
        manufacturer_value = selected_text
    etree.SubElement(ident_number, "manufacturerCode").text = xml_text(manufacturer_value)

    part_number = material.part_number
    if tag in {"partAndSerialNumber", "partNumber"}:
        part_number = selected_text
    if part_number:
        part_and_serial = etree.SubElement(ident_number, "partAndSerialNumber")
        etree.SubElement(part_and_serial, "partNumber").text = xml_text(part_number)

    quantity = material.quantity
    if tag == "reqQuantity":
        quantity = selected_text
    quantity_element = etree.SubElement(
        item, "reqQuantity", unitOfMeasure=xml_text(material.unit or "A REMPLACER"),
    )
    quantity_element.text = xml_text(quantity or "A REMPLACER")

    if material.remarks:
        remarks = etree.SubElement(item, "remarks")
        etree.SubElement(remarks, "simplePara").text = xml_text(material.remarks)


def _emit_material_requirements(
    parent: etree._Element,
    *,
    container_tag: str,
    no_tag: str,
    group_tag: str,
    item_tag: str,
    sections: Sequence[IRNode],
    xml_text: TextSanitizer,
    comment: CommentFactory,
    reviewed: bool,
) -> None:
    container = etree.SubElement(parent, container_tag)
    resources = resource_rows(sections)
    materials = [
        row for row in resources
        if (not reviewed or row.target_tag != no_tag) and not _explicitly_no_requirement(row.text)
    ]
    if not materials:
        etree.SubElement(container, no_tag)
        return

    group = etree.SubElement(container, group_tag)
    for material in materials:
        _emit_material_item(
            group, material, item_tag=item_tag, xml_text=xml_text, comment=comment,
            reviewed=reviewed,
        )


def _emit_safety_requirements(
    parent: etree._Element,
    sections: Sequence[IRNode],
    *,
    emit_admonition: EmitAdmonition,
    xml_text: TextSanitizer,
    reviewed: bool,
) -> None:
    requirement = etree.SubElement(parent, "reqSafety")
    texts = [row.text for row in resource_rows(sections)]
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
    for node in sorted(
        admonitions, key=lambda item: {"warning": 0, "caution": 1}.get(item.admonition or "", 2),
    ):
        tag = _selected_safety_tag(node)
        if reviewed and tag:
            node = replace(node, admonition=tag)
        emit_admonition(safety, node)
    for section in sections:
        for node in section.walk()[1:]:
            if node.kind not in {"paragraph", "item"} or _explicitly_no_requirement(node.text):
                continue
            tag = _selected_safety_tag(node)
            if reviewed and tag:
                emit_admonition(
                    safety,
                    replace(node, kind="admonition", admonition=tag),
                )
            else:
                note = etree.SubElement(safety, "note")
                note_para = etree.SubElement(note, "notePara")
                note_para.text = xml_text(node.text)


def emit_preliminary_requirements(
    parent: etree._Element,
    requirements: Mapping[str, Sequence[IRNode]],
    *,
    emit_admonition: EmitAdmonition,
    comment: CommentFactory,
    xml_text: TextSanitizer,
    reviewed: bool,
) -> None:
    preliminary = etree.SubElement(parent, "preliminaryRqmts")
    emit_condition_requirements(
        preliminary, requirements.get("conditions", []), xml_text=xml_text, reviewed=reviewed,
    )
    _emit_personnel_requirements(
        preliminary, requirements.get("personnel", []), xml_text=xml_text, reviewed=reviewed,
    )
    _emit_material_requirements(
        preliminary,
        container_tag="reqSupportEquips",
        no_tag="noSupportEquips",
        group_tag="supportEquipDescrGroup",
        item_tag="supportEquipDescr",
        sections=requirements.get("support", []),
        xml_text=xml_text,
        comment=comment,
        reviewed=reviewed,
    )
    _emit_material_requirements(
        preliminary,
        container_tag="reqSupplies",
        no_tag="noSupplies",
        group_tag="supplyDescrGroup",
        item_tag="supplyDescr",
        sections=requirements.get("supplies", []),
        xml_text=xml_text,
        comment=comment,
        reviewed=reviewed,
    )
    _emit_material_requirements(
        preliminary,
        container_tag="reqSpares",
        no_tag="noSpares",
        group_tag="spareDescrGroup",
        item_tag="spareDescr",
        sections=requirements.get("spares", []),
        xml_text=xml_text,
        comment=comment,
        reviewed=reviewed,
    )
    _emit_safety_requirements(
        preliminary,
        requirements.get("safety", []),
        emit_admonition=emit_admonition,
        xml_text=xml_text,
        reviewed=reviewed,
    )
