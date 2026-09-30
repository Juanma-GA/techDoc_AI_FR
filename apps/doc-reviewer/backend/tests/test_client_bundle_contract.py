from __future__ import annotations

from collections.abc import Mapping

import pytest
from pydantic import ValidationError

from app.checks.client_bundle import (
    ClientBundle,
    ClientCatalog,
    ClientMapping,
    ClientMappingField,
    ClientOperation,
    ClientRuleDefinition,
    OperationResult,
)
from app.core.compiled_rules import Check, CompiledRule, RuleTarget


def _rule(code: str = "CLIENT_RULE") -> ClientRuleDefinition:
    compiled_rule = CompiledRule(
        id=code,
        topic="Client rule",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[Check(field="text", operator="exists", expected="required")],
        source="standard_rule",
    )
    return ClientRuleDefinition(
        compiled_rule=compiled_rule,
        name="Client rule",
        description="A client-specific check.",
        message="Required text is missing.",
        kind="compiled",
    )


def _bundle(
    rules: tuple[ClientRuleDefinition, ...] = (_rule(),),
    operations: Mapping[str, ClientOperation[object]] | None = None,
) -> ClientBundle[object]:
    return ClientBundle(
        client_code="example",
        bundle_version="1.0.0",
        contract_version="1",
        manifest_hash="manifest-hash",
        mapping_hash="mapping-hash",
        bundle_hash="bundle-hash",
        catalogs=(ClientCatalog(code="EXAMPLE", version="v1"),),
        mapping=ClientMapping(),
        rules=rules,
        operations=operations or {},
        standard_specs={},
    )


def test_client_mapping_validates_field_types_and_entity_patterns() -> None:
    mapping = ClientMapping(
        fields={
            "pnrs": ClientMappingField(type="string_list", max_items=4),
            "document_type": ClientMappingField(
                type="enum",
                allowed_values=["CMM", "OHM"],
                default="CMM",
            ),
        },
        entities={"cmm_number": r"(\d{2}-\d{2}-\d{2})"},
    )

    assert mapping.fields["pnrs"].type == "string_list"
    assert mapping.fields["document_type"].default == "CMM"

    with pytest.raises(ValidationError, match="enum fields require allowed_values"):
        ClientMappingField(type="enum")
    with pytest.raises(ValidationError, match="invalid entity pattern"):
        ClientMapping(entities={"broken": "["})


def test_operation_result_keeps_verdict_and_suggestion_span_together() -> None:
    result = OperationResult(
        status="FAIL",
        observed="12 bar",
        expected="12 bar (174 psi)",
        message="Pressure conversion is missing.",
        original="12 bar",
        proposed="12 bar (174 psi)",
        span=(10, 16),
    )

    assert result.status == "FAIL"
    assert result.span == (10, 16)

    with pytest.raises(ValidationError, match="non-negative start/end pair"):
        OperationResult(status="FAIL", span=(8, 4))


def test_client_rule_definition_generates_presentation_metadata() -> None:
    definition = _rule()

    assert definition.code == "CLIENT_RULE"
    assert definition.metadata["description"] == "A client-specific check."
    assert definition.metadata["kind"] == "compiled"
    assert definition.metadata["severity"] == "warning"


def test_client_bundle_rejects_duplicate_rule_codes() -> None:
    duplicate = _rule()

    with pytest.raises(ValueError, match="rule codes must be unique"):
        _bundle(rules=(duplicate, duplicate))


def test_client_bundle_rejects_mismatched_operation_registry_key() -> None:
    def execute(_context: object, _params: Mapping[str, object]) -> OperationResult:
        return OperationResult(status="PASS")

    operation = ClientOperation(name="actual_name", execute=execute)

    with pytest.raises(ValueError, match="keys must match operation names"):
        _bundle(operations={"wrong_name": operation})


def test_client_bundle_rejects_rule_referencing_unknown_operation() -> None:
    compiled_rule = CompiledRule(
        id="CLIENT_OPERATION_RULE",
        topic="Operation rule",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[
            Check(
                field="text",
                operator="client_operation",
                operation="missing_operation",
            )
        ],
        source="standard_rule",
    )
    definition = ClientRuleDefinition(
        compiled_rule=compiled_rule,
        name="Operation rule",
        description="Uses a bundle operation.",
        message="Operation failed.",
        kind="compiled",
    )

    with pytest.raises(ValueError, match="references unknown operation.*missing_operation"):
        _bundle(rules=(definition,))


def test_client_bundle_rejects_rule_referencing_undeclared_mapping_field() -> None:
    compiled_rule = CompiledRule(
        id="CLIENT_ENTITY_RULE",
        topic="Entity rule",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[Check(field="serial_number", operator="exists")],
        source="standard_rule",
    )
    definition = ClientRuleDefinition(
        compiled_rule=compiled_rule,
        name="Serial number",
        description="Checks a declared client entity.",
        message="Serial number is missing.",
        kind="compiled",
    )

    with pytest.raises(ValueError, match="references undeclared text field: serial_number"):
        _bundle(rules=(definition,))