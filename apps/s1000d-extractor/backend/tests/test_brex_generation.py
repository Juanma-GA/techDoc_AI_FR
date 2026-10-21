from __future__ import annotations

from collections.abc import Callable

from app.core.brex import BrexRule
from app.core.brex_generation import (
    apply_brex_candidate_guidance,
    serialize_with_brex_guidance,
)
from app.core.brex_validation import validate_brex
from app.core.ir import Candidate, IRNode
from app.core.s1000d_serializer import SerializationDiagnostics


def _forbid(element: str) -> list[BrexRule]:
    return [
        BrexRule(
            object_path=f"//{element}",
            allowed_flag="0",
            object_use=f"{element} is forbidden.",
        )
    ]


def _render_candidate(root: IRNode) -> Callable[[SerializationDiagnostics], str]:
    def render(_diagnostics: SerializationDiagnostics) -> str:
        element = root.candidates[0].element
        return f"<dmodule><content><{element}/></content></dmodule>"

    return render


def test_brex_guidance_selects_an_existing_candidate_that_avoids_a_violation() -> None:
    root = IRNode(
        id="paragraph",
        kind="paragraph",
        candidates=[
            Candidate("forbiddenElement", 0.9, "Preferred mapping"),
            Candidate("allowedElement", 0.4, "Alternative mapping"),
        ],
    )

    xml, _diagnostics, changed_count = apply_brex_candidate_guidance(
        root,
        _forbid("forbiddenElement"),
        _render_candidate(root),
    )

    assert changed_count == 1
    assert root.candidates[0].element == "allowedElement"
    assert "BREX" in root.candidates[0].rationale
    assert validate_brex(xml, _forbid("forbiddenElement")) == []


def test_serializer_guidance_uses_a_valid_alternative_for_a_brex_rule() -> None:
    paragraph = IRNode(
        id="paragraph",
        kind="paragraph",
        text="Disconnect the connector.",
        context="procedural",
        candidates=[
            Candidate("proceduralStep", 0.6, "Nested step"),
            Candidate("para", 0.4, "Paragraph"),
        ],
    )
    root = IRNode(
        id="root",
        kind="section",
        children=[
            IRNode(
                id="step",
                kind="section",
                text="Removal",
                context="procedural",
                candidates=[Candidate("proceduralStep", 0.8, "Procedure step")],
                children=[paragraph],
            )
        ],
    )
    rules = [
        BrexRule(
            object_path="//proceduralStep/proceduralStep",
            allowed_flag="0",
            object_use="Nested procedural steps are forbidden.",
        )
    ]

    xml, diagnostics, changed_count = serialize_with_brex_guidance(
        root,
        rules,
        issue="4.2",
        dm_type="procedural",
    )

    assert changed_count == 1
    assert paragraph.candidates[0].element == "para"
    assert "Disconnect the connector." in xml
    assert not [
        violation for violation in diagnostics.xsd_violations
        if violation.get("severity") == "error"
    ]
    assert not [
        violation for violation in validate_brex(xml, rules, allow_internal_dtd=True)
        if violation.get("severity") == "error"
    ]


def test_brex_guidance_preserves_an_explicit_human_choice() -> None:
    root = IRNode(
        id="paragraph",
        kind="paragraph",
        candidates=[
            Candidate("forbiddenElement", 1.0, "Choix humain"),
            Candidate("allowedElement", 0.4, "Alternative mapping"),
        ],
    )

    xml, _diagnostics, changed_count = apply_brex_candidate_guidance(
        root,
        _forbid("forbiddenElement"),
        _render_candidate(root),
    )

    assert changed_count == 0
    assert root.candidates[0].element == "forbiddenElement"
    assert validate_brex(xml, _forbid("forbiddenElement"))


def test_brex_guidance_will_not_worsen_xsd_errors_to_avoid_a_brex_error() -> None:
    root = IRNode(
        id="paragraph",
        kind="paragraph",
        candidates=[
            Candidate("forbiddenElement", 0.9, "Preferred mapping"),
            Candidate("allowedElement", 0.4, "Alternative mapping"),
        ],
    )

    def render(diagnostics: SerializationDiagnostics) -> str:
        element = root.candidates[0].element
        if element == "allowedElement":
            diagnostics.xsd_violations.append({
                "severity": "error",
                "rule": "XSD",
                "message": "The alternative is not valid in the target content model.",
                "path": "/dmodule/content",
            })
        return f"<dmodule><content><{element}/></content></dmodule>"

    xml, _diagnostics, changed_count = apply_brex_candidate_guidance(
        root,
        _forbid("forbiddenElement"),
        render,
    )

    assert changed_count == 0
    assert root.candidates[0].element == "forbiddenElement"
    assert validate_brex(xml, _forbid("forbiddenElement"))


def test_brex_guidance_does_not_invent_a_missing_required_object() -> None:
    root = IRNode(id="paragraph", kind="paragraph", text="Source content")
    required = [
        BrexRule(
            object_path="//requiredObject",
            allowed_flag="1",
            object_use="Required content.",
        )
    ]

    xml, _diagnostics, changed_count = apply_brex_candidate_guidance(
        root,
        required,
        lambda _diagnostics: "<dmodule><content/></dmodule>",
    )

    assert changed_count == 0
    violations = validate_brex(xml, required)
    assert any(violation["rule"] == "BREX" for violation in violations)
