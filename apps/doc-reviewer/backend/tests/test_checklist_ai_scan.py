"""Checklist AI_SCAN mode keeps deterministic and AI execution paths separate."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.core import rules_engine
from app.core.compiled_rules import Check, CompiledRule, RuleTarget
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def _rule(*, source_instruction: str = "Le footer doit contenir la mention requise.") -> CompiledRule:
    return CompiledRule(
        id="CHECKLIST_AI_MODE",
        topic="Footer",
        execution="deterministic",
        target=RuleTarget(page="all", region="footer"),
        checks=[Check(field="text", operator="exists", expected="required")],
        source="user_checklist",
        source_instruction=source_instruction,
    )


def test_checklist_ai_scan_setting_defaults_off_and_persists(client: TestClient) -> None:
    initial = client.get("/api/v1/settings/mistral")
    assert initial.status_code == 200
    assert initial.json()["checklist_ai_scan"] is False

    updated = client.post(
        "/api/v1/settings/mistral",
        json={"checklist_ai_scan": True},
    )
    assert updated.status_code == 200
    assert updated.json()["checklist_ai_scan"] is True
    assert client.get("/api/v1/settings/mistral").json()["checklist_ai_scan"] is True


def test_route_compiled_rules_moves_only_deterministic_checklist_rules() -> None:
    checklist = _rule()
    standard = CompiledRule(
        id="STANDARD_RULE",
        topic="Standard",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[Check(field="text", operator="exists", expected="standard")],
        source="standard_rule",
    )
    semantic = checklist.model_copy(
        update={
            "id": "CHECKLIST_SEMANTIC",
            "execution": "semantic",
            "checks": [],
            "semantic_instruction": "Évaluer le sens.",
        }
    )

    executable, ai_rules = rules_engine.route_compiled_rules(
        [checklist, standard, semantic],
        checklist_ai_scan=True,
    )

    assert [rule.id for rule in executable] == ["STANDARD_RULE", "CHECKLIST_SEMANTIC"]
    assert [rule["id"] for rule in ai_rules] == ["CHECKLIST_AI_MODE"]
    assert ai_rules[0]["instruction"] == "Le footer doit contenir la mention requise."


def test_ai_scan_receives_compiled_checklist_instruction(monkeypatch) -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="The footer text", spans=[])],
        full_text="The footer text",
        is_signed=False,
    )
    captured: dict[str, Any] = {}

    def _scan(*_args: Any, **kwargs: Any) -> list[dict[str, str]]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(rules_engine, "get_ai_custom_prompt", lambda _db: "")
    monkeypatch.setattr(rules_engine, "scan_with_prompt", _scan)

    results = rules_engine._run_ai_custom(
        parsed,
        object(),
        [],
        [],
        compiled_checklist_rules=[
            {
                "id": "CHECKLIST_AI_MODE",
                "severity": "warning",
                "title": "Footer",
                "instruction": "Le footer doit contenir la mention requise.",
            }
        ],
    )

    assert results == []
    assert captured["compiled_checklist_rules"][0]["instruction"] == (
        "Le footer doit contenir la mention requise."
    )