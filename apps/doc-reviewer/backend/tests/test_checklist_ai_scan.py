"""Checklist AI_SCAN mode keeps deterministic and AI execution paths separate."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import llm_suggester, rules_engine
from app.core.compiled_rules import Check, CompiledRule, RuleTarget
from app.core.errors import AppError
from app.core.compiled_rule_runtime import _TextTarget
from app.core.compiled_rule_semantic import execute_semantic, semantic_groups
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


def test_ai_scan_segments_cover_all_page_text() -> None:
    source = "synthetic paragraph " * 7 + "END"
    pages = [
        ParsedPage(page=1, text=source, spans=[]),
        ParsedPage(page=2, text="later page", spans=[]),
    ]

    groups = rules_engine._group_pages_by_text_budget(pages, 16)
    segments = [page for group in groups for page in group]
    reconstructed = {
        page: "".join(segment.text or "" for segment in segments if segment.page == page)
        for page in (1, 2)
    }

    assert reconstructed == {1: source, 2: "later page"}
    assert all(len("\n".join(page.text or "" for page in group)) <= 16 for group in groups)


def test_ai_scan_sends_all_text_over_previous_page_limit(monkeypatch) -> None:
    source = "SYNTHETIC-DOCUMENT-CONTENT-" * 200
    captured: dict[str, str] = {}

    monkeypatch.setattr(llm_suggester, "get_llm_enabled", lambda _db: True)

    def fake_call(_db: object, _system: str, user_payload: str) -> str:
        captured["text"] = json.loads(user_payload)["text"]
        return '{"items": []}'

    monkeypatch.setattr(llm_suggester, "_call_mistral", fake_call)

    assert llm_suggester.scan_with_prompt(object(), "synthetic rule", source) == []
    assert captured["text"] == source


def test_disabled_ai_scan_reports_incomplete_coverage_without_fallback(monkeypatch) -> None:
    source = "SYNTHETIC-DOCUMENT-CONTENT"
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text=source, spans=[])],
        full_text=source,
        is_signed=False,
    )
    warnings: list[str] = []

    monkeypatch.setattr(rules_engine, "get_ai_custom_prompt", lambda _db: "synthetic rule")
    monkeypatch.setattr(llm_suggester, "get_llm_enabled", lambda _db: False)

    result = rules_engine._run_ai_custom(
        parsed,
        object(),
        [],
        [],
        document=SimpleNamespace(document_language="fr"),
        warnings=warnings,
    )

    assert result == []
    assert len(warnings) == 1
    assert "partiellement indisponible" in warnings[0]
    assert "LLM_DISABLED" not in warnings[0]


def test_malformed_ai_scan_response_is_not_reported_as_clean(monkeypatch) -> None:
    monkeypatch.setattr(llm_suggester, "get_llm_enabled", lambda _db: True)
    monkeypatch.setattr(llm_suggester, "_call_mistral", lambda *_args: "not-json")

    with pytest.raises(AppError, match="inexploitable") as exc_info:
        llm_suggester.scan_with_prompt(object(), "synthetic rule", "synthetic document")

    assert exc_info.value.code == "LLM_RESPONSE_INVALID"


def test_semantic_segments_cover_text_beyond_previous_total_budget() -> None:
    source = "synthetic semantic paragraph " * 5_000
    target = _TextTarget(page="1", text=source, raw_page=1)

    groups = semantic_groups([target])
    segments = [segment for group in groups for segment in group]

    assert "".join(segment.text for segment in segments) == source
    assert all(len(segment.text) <= 10_000 for segment in segments)
    assert [segment.text_offset for segment in segments] == sorted(
        segment.text_offset for segment in segments
    )
    assert len(segments) > 12


def test_semantic_result_is_inconclusive_when_any_segment_fails(monkeypatch) -> None:
    source = "SYNTHETIC-ISSUE " + "x" * 10_020 + " END"
    target = _TextTarget(page="1", text=source, raw_page=1)
    rule = CompiledRule(
        id="CHECKLIST_SEMANTIC_SEGMENTS",
        topic="Synthetic semantic rule",
        execution="semantic",
        target=RuleTarget(page="all", region="full_page"),
        semantic_instruction="Inspect synthetic content.",
        source="user_checklist",
    )
    calls = 0

    def fake_chat(*_args: Any, **_kwargs: Any) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            return json.dumps(
                {
                    "violations": [
                        {
                            "page": "1",
                            "original": "SYNTHETIC-ISSUE",
                            "proposed": "",
                            "message": "Synthetic finding",
                        }
                    ]
                }
            )
        raise AppError("LLM_DISABLED", "Synthetic unavailable")

    monkeypatch.setattr("app.core.compiled_rule_executor.call_chat", fake_chat)

    result, suggestions = execute_semantic(
        rule,
        [target],
        object(),
        is_docx=True,
        pdf_pages=None,
        document=None,
    )

    assert calls > 1
    assert result.status == "INCONCLUSIVE"
    assert len(suggestions) == 1
    assert suggestions[0].span == (0, len("SYNTHETIC-ISSUE"))
    assert suggestions[0].ai_generated is True


def test_ai_source_classification_distinguishes_generated_from_checklist_rules() -> None:
    assert rules_engine.classify_source("custom", "AI_SCAN", ai_generated=True) == "ai"
    assert rules_engine.classify_source("compiled_checklist", "CHECKLIST_1") == "checklist"