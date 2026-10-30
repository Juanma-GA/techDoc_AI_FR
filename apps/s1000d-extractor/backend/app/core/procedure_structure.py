"""Keep source warnings, steps and editorial wrappers in their proper roles."""

from __future__ import annotations

from dataclasses import replace

from app.core.errors import AppError
from app.core.ir import Candidate, IRNode
from app.core.procedure_semantics import LAYOUT_ZONES, heading_text, is_main_container


def is_numbered_procedure_group(node: IRNode) -> bool:
    if node.kind != "section" or node.text or node.context != "procedural" or len(node.children) != 2:
        return False
    introduction, sequence = node.children
    return (
        introduction.kind == "paragraph"
        and introduction.text.rstrip().endswith(":")
        and sequence.kind == "item-sequence"
        and sequence.form == "ordered"
        and bool(sequence.children)
    )


def common_information_nodes(children: list[IRNode]) -> list[IRNode]:
    result = []
    for node in children:
        target = {
            "section": "commonInfoDescrPara",
            "paragraph": "para",
            "item-sequence": "sequentialList" if node.form == "ordered" else "randomList",
        }.get(node.kind)
        result.append(replace(
            node, children=common_information_nodes(node.children),
            candidates=[Candidate(target, 1.0)] if target else node.candidates,
        ))
    return result


def procedure_steps(children: list[IRNode], *, main: bool = True) -> list[IRNode]:
    result: list[IRNode] = []
    pending: list[IRNode] = []
    for node in children:
        if node.zone in LAYOUT_ZONES:
            continue
        if node.kind == "admonition":
            pending.append(node)
            continue
        if node.kind == "section":
            if is_main_container(node.text) or (node.text.strip() and not heading_text(node.text)):
                result.extend(procedure_steps([*pending, *node.children], main=main))
                pending = []
                continue
            node = replace(node, children=(
                [*pending, *node.children] if is_numbered_procedure_group(node)
                else procedure_steps([*pending, *node.children], main=False)
            ))
        elif node.kind == "paragraph" and (
            main or pending or (node.candidates and node.candidates[0].element == "proceduralStep")
        ):
            paragraph = replace(node, candidates=[Candidate("para", 1.0)])
            node = IRNode(id=f"step-{node.id}", kind="section", context="procedural",
                          candidates=[Candidate("proceduralStep", 1.0)],
                          children=[*pending, paragraph])
        elif node.kind == "item-sequence" and node.form == "ordered":
            items = [
                IRNode(id=f"step-{item.id}", kind="section", context="procedural",
                       candidates=[Candidate("proceduralStep", 1.0)],
                       children=[replace(item, kind="paragraph", candidates=[Candidate("para", 1.0)]),
                                 *item.children])
                for item in node.children
            ]
            if items:
                items[0].children = [*pending, *items[0].children]
                result.extend(items)
                pending = []
                continue
        elif node.kind in {"figure", "table"}:
            if result and result[-1].kind == "section" and not is_numbered_procedure_group(result[-1]):
                result[-1].children.extend([*pending, node])
                pending = []
            else:
                result.append(node)
            continue
        elif node.kind == "item-sequence" and result and result[-1].kind == "section":
            result[-1].children.extend([*pending, node])
            pending = []
            continue
        elif (
            node.kind == "paragraph" and result and result[-1].kind == "section"
            and not is_numbered_procedure_group(result[-1])
        ):
            result[-1].children.append(node)
            continue
        elif node.kind == "item-sequence" and main:
            node = IRNode(id=f"step-{node.id}", kind="section", context="procedural",
                          candidates=[Candidate("proceduralStep", 1.0)],
                          children=[*pending, node])
        else:
            result.extend(pending)
        pending = []
        result.append(node)
    if pending:
        step = next((node for node in reversed(result) if node.kind == "section"), None)
        if step is not None:
            step.children.extend(pending)
        elif not main:
            result.extend(pending)
        else:
            raise AppError(
                "PROCEDURE_ACTION_REQUIRED",
                "Un avertissement de procedure doit etre associe a une etape. Verifiez son classement.",
                422,
            )
    return result
