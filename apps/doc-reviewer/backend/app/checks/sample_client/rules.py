"""Small sample catalog demonstrating bundle-owned declarations."""

from app.checks.client_bundle import ClientRuleDefinition
from app.core.compiled_rules import Check, CompiledRule, RuleTarget


SAMPLE_RULE = ClientRuleDefinition(
    compiled_rule=CompiledRule(
        id="SAMPLE_SERIAL_MARKER",
        topic="Sample serial and marker check",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[
            Check(field="serial_number", operator="exists"),
            Check(
                field="text",
                operator="client_operation",
                operation="sample_marker",
                operation_params={"expected": "SAMPLE MARKER"},
            ),
        ],
        source="standard_rule",
    ),
    name="Sample serial and marker check",
    description="Checks an entity declared in mapping.json and a bundle operation.",
    message="The sample marker is missing.",
    kind="content",
)

RULE_DEFINITIONS = (SAMPLE_RULE,)
RULE_METADATA = {SAMPLE_RULE.code: SAMPLE_RULE.metadata}
CATALOG = {"v1": [SAMPLE_RULE.compiled_rule]}
STANDARD_SPEC: dict[str, object] = {
    "code": "SAMPLE-CHECKS",
    "label": "Sample client checks",
    "description": "A minimal example client bundle.",
    "versions": CATALOG,
    "metadata": RULE_METADATA,
}