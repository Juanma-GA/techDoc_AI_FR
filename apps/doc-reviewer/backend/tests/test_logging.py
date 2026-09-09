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


def test_sanitize_llm_debug_keeps_text_and_removes_secrets_and_image_bytes() -> None:
    payload = {
        "messages": [{"role": "user", "content": "Keep this prompt"}],
        "authorization": "Bearer secret-key",
        "image_url": "data:image/png;base64,ABCDEF",
    }

    sanitized = sanitize_llm_debug(payload)

    assert sanitized["messages"][0]["content"] == "Keep this prompt"
    assert sanitized["authorization"] == "<redacted>"
    assert sanitized["image_url"] == {"inline_image": "image/png", "base64_chars": 6}


def test_text_llm_call_logs_payload_and_response_without_api_key(monkeypatch, capsys) -> None:
    from app.core import llm_suggester
    from app.core.logging import configure_logging

    class FakeResponse:
        status_code = 200
        text = '{"choices":[{"message":{"content":"response text"}}]}'

        def json(self):
            return {"choices": [{"message": {"content": "response text"}}]}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(llm_suggester, "get_llm_enabled", lambda db: True)
    monkeypatch.setattr(
        llm_suggester,
        "get_effective",
        lambda db: {
            "api_key": "sk-secret-test-value",
            "base_url": "https://example.test",
            "chat_model": "test-model",
        },
    )
    monkeypatch.setattr(llm_suggester.httpx, "Client", lambda timeout: FakeClient())

    configure_logging("DEBUG")
    try:
        result = llm_suggester._call_mistral(object(), "system prompt", "user prompt")
    finally:
        configure_logging("WARNING")

    output = capsys.readouterr().out
    assert result == "response text"
    assert "llm_request" in output
    assert "system prompt" in output
    assert "user prompt" in output
    assert "llm_response" in output
    assert "response text" in output
    assert "sk-secret-test-value" not in output