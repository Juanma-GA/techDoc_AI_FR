"""Guide ambiguous IR mappings with a selected BREX before XML is finalized."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime

from app.core.brex import BrexRule
from app.core.brex_validation import compile_brex_validator
from app.core.ir import IRNode
from app.core.s1000d_serializer import (
    ReferenceIndex,
    SerializationDiagnostics,
    serialize,
)

RenderBrexXml = Callable[[SerializationDiagnostics], str]


def _error_count(violations: Sequence[Mapping[str, object]]) -> int:
    return sum(violation.get("severity") == "error" for violation in violations)


def apply_brex_candidate_guidance(
    root: IRNode,
    rules: list[BrexRule],
    render: RenderBrexXml,
) -> tuple[str, SerializationDiagnostics, int]:
    """Select existing candidates when they improve BREX without harming XSD."""
    candidates = [
        node for node in root.walk()
        if len(node.candidates) > 1
        and not node.candidates[0].rationale.startswith("Choix humain")
    ]
    validator = compile_brex_validator(rules) if rules and candidates else None
    diagnostics = SerializationDiagnostics()
    xml = render(diagnostics)
    if validator is None:
        return xml, diagnostics, 0

    brex_errors = _error_count(validator.validate(xml, allow_internal_dtd=True))
    if not brex_errors:
        return xml, diagnostics, 0

    xsd_errors = _error_count(diagnostics.xsd_violations)
    guided_count = 0
    for node in candidates:
        original = list(node.candidates)
        best_index = 0
        best_brex_errors = brex_errors
        best_xsd_errors = xsd_errors
        for candidate_index, candidate in enumerate(original[1:], start=1):
            node.candidates = [
                candidate,
                *(item for index, item in enumerate(original) if index != candidate_index),
            ]
            trial_diagnostics = SerializationDiagnostics()
            trial_xml = render(trial_diagnostics)
            trial_xsd_errors = _error_count(trial_diagnostics.xsd_violations)
            if trial_xsd_errors > best_xsd_errors:
                continue
            trial_brex_errors = _error_count(
                validator.validate(trial_xml, allow_internal_dtd=True)
            )
            if trial_brex_errors < best_brex_errors:
                best_index = candidate_index
                best_brex_errors = trial_brex_errors
                best_xsd_errors = trial_xsd_errors

        if best_index == 0:
            node.candidates = original
            continue

        selected = original[best_index]
        rationale = selected.rationale.strip()
        guided = replace(
            selected,
            rationale=(
                f"{rationale} (choix guidé par le BREX)"
                if rationale
                else "Choix guidé par le BREX"
            ),
        )
        node.candidates = [
            guided,
            *(item for index, item in enumerate(original) if index != best_index),
        ]
        node.confidence = selected.score
        brex_errors = best_brex_errors
        xsd_errors = best_xsd_errors
        guided_count += 1

    if not guided_count:
        return xml, diagnostics, 0

    final_diagnostics = SerializationDiagnostics()
    final_xml = render(final_diagnostics)
    return final_xml, final_diagnostics, guided_count


def serialize_with_brex_guidance(
    root: IRNode,
    rules: list[BrexRule],
    *,
    issue: str,
    dm_type: str,
    title: str = "",
    figure_offset: int = 0,
    table_offset: int = 0,
    section_offset: int = 0,
    dm_metadata: Mapping[str, object] | None = None,
    missing_fields: Sequence[str] = (),
    header_template: Mapping[str, object] | None = None,
    reference_index: ReferenceIndex | None = None,
    reference_dm_id: str = "",
    created_at: datetime | None = None,
) -> tuple[str, SerializationDiagnostics, int]:
    def render(diagnostics: SerializationDiagnostics) -> str:
        return serialize(
            root,
            issue=issue,
            dm_type=dm_type,
            title=title,
            figure_offset=figure_offset,
            table_offset=table_offset,
            section_offset=section_offset,
            dm_metadata=dm_metadata,
            missing_fields=missing_fields,
            header_template=header_template,
            reference_index=reference_index,
            reference_dm_id=reference_dm_id,
            created_at=created_at,
            diagnostics=diagnostics,
        )

    return apply_brex_candidate_guidance(root, rules, render)
