"""Slide cloning helpers that preserve editable PowerPoint content."""
from __future__ import annotations

from copy import deepcopy

from pptx.opc.constants import RELATIONSHIP_TYPE as RT


def clone_slide(presentation, source):
    target = presentation.slides.add_slide(source.slide_layout)
    target_tree = target.shapes._spTree
    for shape in list(target.shapes):
        target_tree.remove(shape.element)
    for shape in source.shapes:
        target_tree.insert_element_before(deepcopy(shape.element), "p:extLst")
    if source._element.cSld.bg is not None:
        target._element.cSld.insert(0, deepcopy(source._element.cSld.bg))

    relationship_ids: dict[str, str] = {}
    for relationship in source.part.rels.values():
        if relationship.reltype in (RT.SLIDE_LAYOUT, RT.NOTES_SLIDE):
            continue
        if relationship.is_external:
            new_id = target.part.rels.get_or_add_ext_rel(
                relationship.reltype, relationship.target_ref
            )
        else:
            new_id = target.part.rels.get_or_add(
                relationship.reltype, relationship.target_part
            )
        relationship_ids[relationship.rId] = new_id

    for element in target._element.cSld.iter():
        for attribute, value in element.attrib.items():
            if value in relationship_ids:
                element.set(attribute, relationship_ids[value])
    return target


def retain_slides(presentation, retained) -> None:
    retained_ids = {id(slide) for slide in retained}
    slide_ids = presentation.slides._sldIdLst
    for slide_id, slide in list(zip(list(slide_ids), list(presentation.slides))):
        if id(slide) in retained_ids:
            continue
        presentation.part.drop_rel(slide_id.rId)
        slide_ids.remove(slide_id)


def reorder_slides(presentation, ordered) -> None:
    slide_ids = presentation.slides._sldIdLst
    by_slide = {
        id(slide): slide_id
        for slide_id, slide in zip(list(slide_ids), list(presentation.slides))
    }
    for slide_id in list(slide_ids):
        slide_ids.remove(slide_id)
    for slide in ordered:
        slide_ids.append(by_slide[id(slide)])
