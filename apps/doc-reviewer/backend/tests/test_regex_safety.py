"""Synthetic tests for bounded user-provided regex rules."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.checks.custom_rules import run as run_custom_rules
from app.core.compiled_rule_executor import execute_pdf_rules
from app.core.compiled_rules import Check, CompiledRule, RuleTarget
from app.core.regex_safety import (
    MAX_USER_REGEX_LENGTH,
    USER_REGEX_INCOMPLETE_WARNING,
    UserRegexPatternError,
    compile_user_regex,
)
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def test_user_regex_rejects_patterns_over_configured_length() -> None:
    with pytest.raises(UserRegexPatternError) as exc_info:
        compile_user_regex("a" * (MAX_USER_REGEX_LENGTH + 1))

    assert exc_info.value.code == "RULE_PATTERN_TOO_LONG"


def test_rule_api_rejects_overlong_regex_before_persistence(client: TestClient) -> None:
    response = client.post(
        "/api/v1/rules",
        json={
            "name": "Synthetic oversized regex",
            "kind": "regex_flag",
            "pattern": "a" * (MAX_USER_REGEX_LENGTH + 1),
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_custom_regex_timeout_marks_analysis_coverage_reduced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.checks import custom_rules

    monkeypatch.setattr(custom_rules, "USER_REGEX_TIMEOUT_SECONDS", 0.001)
    rule = SimpleNamespace(
        enabled=True,
        kind="regex_flag",
        pattern=r"(a|aa)+$",
        id=uuid.uuid4(),
        severity="warning",
        message="synthetic rule",
        name="Synthetic timeout rule",
    )
    page = ParsedPage(page=1, text="a" * 5_000 + "!", spans=[])
    warnings: list[str] = []

    suggestions = run_custom_rules([rule], [page], warnings=warnings)

    assert suggestions == []
    assert warnings == [USER_REGEX_INCOMPLETE_WARNING]


def test_compiled_regex_timeout_returns_inconclusive_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import compiled_rule_operators

    monkeypatch.setattr(compiled_rule_operators, "USER_REGEX_TIMEOUT_SECONDS", 0.001)
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="a" * 5_000 + "!", spans=[])],
        full_text="a" * 5_000 + "!",
        is_signed=False,
    )
    rule = CompiledRule(
        id="CHECKLIST_REGEX_TIMEOUT",
        topic="Synthetic timeout rule",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[Check(field="text", operator="regex", expected=r"(a|aa)+$")],
        source="user_checklist",
    )

    results, suggestions = execute_pdf_rules(parsed, [rule], db=object())

    assert results[0].status == "INCONCLUSIVE"
    assert suggestions == []
