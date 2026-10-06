"""Tests for developer logging configuration and LLM payload sanitisation."""

from __future__ import annotations

import logging

from app.core.logging import parse_log_level, sanitize_llm_debug


def test_log_level_controls_fastapi_debug_mode() -> None:
    from app.config import Settings

    assert Settings(log_level="DEBUG").debug is True
    assert Settings(log_level="INFO").debug is False
    assert Settings(log_level="NONE").debug is False


def test_parse_log_level_supports_debug_and_disabled_aliases() -> None:
    assert parse_log_level("DEBUG") == logging.DEBUG
    assert parse_log_level("NONE") > logging.CRITICAL
    assert parse_log_level("OFF") > logging.CRITICAL
    assert parse_log_level("unexpected") == logging.INFO


def test_none_level_suppresses_structlog_output(capsys) -> None:
    import structlog

    from app.core.logging import configure_logging

    configure_logging("NONE")
    try:
        structlog.get_logger("test").warning("should_be_hidden")
    finally:
        configure_logging("WARNING")

    assert capsys.readouterr().out == ""


def test_uvicorn_access_logs_do_not_emit_resource_paths(capsys) -> None:
    from app.core.logging import configure_logging

    access_logger = logging.getLogger("uvicorn.access")
    configure_logging("INFO")
    try:
        access_logger.info('GET /api/v1/documents/DOCUMENT-ID-SECRET "HTTP/1.1" 200')
    finally:
        configure_logging("WARNING")

    assert "DOCUMENT-ID-SECRET" not in capsys.readouterr().out


def test_sanitize_llm_debug_redacts_text_and_secrets_and_summarizes_images() -> None:
    payload = {
        "messages": [{"role": "user", "content": "Keep this prompt"}],
        "authorization": "Bearer secret-key",
        "image_url": "data:image/png;base64,ABCDEF",
    }

    sanitized = sanitize_llm_debug(payload)

    assert sanitized["messages"][0]["content"] == {"text_chars": len("Keep this prompt")}
    assert sanitized["authorization"] == "<redacted>"
    assert sanitized["image_url"] == {"inline_image": "image/png", "base64_chars": 6}


def test_text_and_vision_llm_calls_do_not_log_sensitive_content(monkeypatch, capsys) -> None:
    import httpx

    from app.core import llm_suggester, mistral_vision
    from app.core.logging import configure_logging

    class FakeResponse:
        status_code = 200
        text = '{"choices":[{"message":{"content":"RESPONSE-SECRET-MARKER"}}]}'

        def json(self):
            return {"choices": [{"message": {"content": "RESPONSE-SECRET-MARKER"}}]}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    def mock_client(*, timeout, follow_redirects):
        assert follow_redirects is False
        return FakeClient()

    synthetic_settings = {
        "api_key": "API-KEY-SECRET-MARKER",
        "base_url": "https://api.mistral.ai",
        "chat_model": "test-model",
        "vision_model": "test-vision-model",
    }
    monkeypatch.setattr(llm_suggester, "get_llm_enabled", lambda _db: True)
    monkeypatch.setattr(llm_suggester, "get_endpoint", lambda _db: synthetic_settings)
    monkeypatch.setattr(mistral_vision, "get_llm_enabled", lambda _db: True)
    monkeypatch.setattr(mistral_vision, "get_endpoint", lambda _db: synthetic_settings)
    monkeypatch.setattr(httpx, "Client", mock_client)

    configure_logging("DEBUG")
    try:
        chat_result = llm_suggester._call_mistral(
            object(), "SYSTEM-SECRET-MARKER", "DOCUMENT-SECRET-MARKER"
        )
        vision_result = mistral_vision._call_mistral_vision(
            object(),
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "PROMPT-SECRET-MARKER METADATA-SECRET-MARKER"},
                        {
                            "type": "image_url",
                            "image_url": "data:image/png;base64,IMAGE-SECRET-MARKER",
                        },
                    ],
                }
            ],
        )
    finally:
        configure_logging("WARNING")

    output = capsys.readouterr().out
    assert chat_result == "RESPONSE-SECRET-MARKER"
    assert vision_result == "RESPONSE-SECRET-MARKER"
    assert "llm_request" in output
    assert "llm_response" in output
    for marker in (
        "SYSTEM-SECRET-MARKER",
        "DOCUMENT-SECRET-MARKER",
        "PROMPT-SECRET-MARKER",
        "METADATA-SECRET-MARKER",
        "IMAGE-SECRET-MARKER",
        "RESPONSE-SECRET-MARKER",
        "API-KEY-SECRET-MARKER",
    ):
        assert marker not in output


def test_analysis_and_compiled_rule_logs_exclude_synthetic_sensitive_values(
    monkeypatch,
    capsys,
) -> None:
    from types import SimpleNamespace

    from app.core import rules_engine
    from app.core.compiled_rule_executor import execute_pdf_rules
    from app.core.compiled_rules import Check, CompiledRule, RuleTarget
    from app.core.logging import configure_logging
    from app.parsers.pdf_parser import ParsedPage, ParsedPdf

    markers = (
        "DOCUMENT-LOG-SECRET",
        "PROMPT-LOG-SECRET",
        "METADATA-LOG-SECRET",
        "RULE-TOPIC-LOG-SECRET",
        "EXPECTED-LOG-SECRET",
        "OBSERVED-LOG-SECRET",
    )
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text=markers[0] + " OBSERVED-LOG-SECRET", spans=[])],
        full_text=markers[0] + " OBSERVED-LOG-SECRET",
        is_signed=False,
    )
    monkeypatch.setattr(rules_engine, "get_ai_custom_prompt", lambda _db: markers[1])
    monkeypatch.setattr(rules_engine, "scan_with_prompt", lambda *_args, **_kwargs: [])
    compiled_rule = CompiledRule(
        id="CHECKLIST_LOG_REDACTION",
        topic=markers[3],
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[Check(field="text", operator="not_exists", expected=markers[4])],
        source="user_checklist",
    )

    configure_logging("DEBUG")
    try:
        rules_engine._run_ai_custom(
            parsed,
            object(),
            [],
            [],
            document=SimpleNamespace(
                document_language="fr",
                meta_cmm_number=markers[2],
                meta_revision_date="REVISION-LOG-SECRET",
            ),
        )
        execute_pdf_rules(
            parsed,
            [compiled_rule],
            db=object(),
            document=SimpleNamespace(meta_cmm_number=markers[2]),
        )
    finally:
        configure_logging("WARNING")

    output = capsys.readouterr().out
    for marker in markers + ("REVISION-LOG-SECRET",):
        assert marker not in output