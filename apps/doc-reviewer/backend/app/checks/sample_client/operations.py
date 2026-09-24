"""Sample operation registry proving client-owned runtime behavior."""

from collections.abc import Mapping
from typing import Any

from app.checks.client_bundle import ClientOperation, OperationResult


def _check_sample_marker(context: Any, parameters: Mapping[str, Any]) -> OperationResult:
    expected = str(parameters.get("expected", "SAMPLE MARKER"))
    for target in context.targets:
        if expected in target.text:
            return OperationResult(
                status="PASS",
                observed=expected,
                expected=expected,
                page=target.raw_page,
            )
    return OperationResult(status="FAIL", expected=expected)


OPERATIONS = {
    "sample_marker": ClientOperation(
        name="sample_marker",
        execute=_check_sample_marker,
    )
}