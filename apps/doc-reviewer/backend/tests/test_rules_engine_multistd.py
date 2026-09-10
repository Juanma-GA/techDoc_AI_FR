"""End-to-end check that the engine only runs rules from the active standard."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.errors import AppError
from app.core import llm_suggester, rules_engine
from app.core.rules_engine import load_compiled_rules, run_all
from app.db.models import Rule, StandardVersion
from app.db.session import SessionLocal
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def _parsed(text: str) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, spans=[])
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


class _DocStub:
    target_unit_system = "auto"

    def __init__(self, document_language: str | None = None) -> None:
        self.document_language = document_language


def _doc(document_language: str | None = None) -> _DocStub:
    return _DocStub(document_language)


def _get_version(session, code: str) -> StandardVersion:
    from sqlalchemy import select

    from app.db.models import Standard

    std = session.scalar(select(Standard).where(Standard.code == code))
    assert std is not None
    return std.versions[0]


def test_mat10000_run_does_not_emit_ata_codes() -> None:
    session = SessionLocal()
    try:
        mat_v = _get_version(session, "MAT10000")
        # Sample text triggers fields/sections from both norms.
        parsed = _parsed(
            "Procedure: Replace the engine.\n"
            "Périodicité: 200 FH.\n"
            "1. Le panneau est retiré.\n"
        )
        out = run_all(parsed, _doc(), session, [mat_v])
        codes = {s.rule_code for s in out}
        assert not any(c.startswith("ATA22_") for c in codes)
        assert not any(c.startswith("ATA_") for c in codes)
    finally:
        session.close()


def test_no_standard_version_only_runs_transverse() -> None:
    session = SessionLocal()
    try:
        parsed = _parsed("A simple line with no fields.")
        out = run_all(parsed, _doc(), session, None)
        # No catalog → no built-in rule code emitted. Custom transverse
        # rules from the demo seed may still flag entries, so we just
        # verify no standard catalog code appears.
        codes = {s.rule_code for s in out}
        assert not any(
            c.startswith(("MAT_", "S2K_", "ATA_", "ATA22_", "STE_", "S1000D_", "PROC_"))
            for c in codes
        )
    finally:
        session.close()


def test_no_standard_version_loads_no_hardcoded_deterministic_rule() -> None:
    session = SessionLocal()
    try:
        assert load_compiled_rules(session, [], checklist_enabled=False) == []
    finally:
        session.close()


def test_compiled_catalog_rule_does_not_fall_through_to_legacy_or_ai(monkeypatch) -> None:
    session = SessionLocal()
    try:
        custom_version = _get_version(session, "ATEXIS-CUSTOM")
        for rule in session.query(Rule):
            rule.enabled = False

        calls = 0

        def _scan(*_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
            nonlocal calls
            calls += 1
            return []

        monkeypatch.setattr(rules_engine, "get_ai_custom_prompt", lambda _db: "")
        monkeypatch.setattr(rules_engine, "get_checklist_ai_scan", lambda _db: False)
        monkeypatch.setattr(rules_engine, "scan_with_prompt", _scan)

        out = run_all(
            _parsed("79-30-02"),
            _doc(),
            session,
            [custom_version],
            checklist_enabled=True,
        )

        assert out == []
        assert calls == 0
    finally:
        session.rollback()
        session.close()


def test_hardcoded_deterministic_rules_belong_to_selected_standard() -> None:
    session = SessionLocal()
    try:
        ata_version = _get_version(session, "ATA100")
        ste_version = _get_version(session, "ASD-STE100")

        ata_rules = load_compiled_rules(session, [ata_version], checklist_enabled=False)
        ste_rules = load_compiled_rules(session, [ste_version], checklist_enabled=False)

        assert ata_rules
        assert ste_rules
        assert all((rule.origin_ref or "").startswith("ATA100:") for rule in ata_rules)
        assert all((rule.origin_ref or "").startswith("ASD-STE100:") for rule in ste_rules)
        assert not {rule.id for rule in ata_rules} & {rule.id for rule in ste_rules}
    finally:
        session.close()


def test_disabled_hardcoded_deterministic_rule_is_not_loaded() -> None:
    session = SessionLocal()
    try:
        ata_version = _get_version(session, "ATA100")
        ata_version.disabled_rule_codes = json.dumps(["ATA_CHAPTER_REF"])

        rules = load_compiled_rules(session, [ata_version], checklist_enabled=False)

        assert "ATA_CHAPTER_REF" not in {rule.id for rule in rules}
    finally:
        session.rollback()
        session.close()


def test_catalog_json_is_well_formed_for_every_builtin() -> None:
    session = SessionLocal()
    try:
        for sv in session.query(StandardVersion).filter(StandardVersion.builtin.is_(True)):
            data: Any = json.loads(sv.catalog_json or "[]")
            assert isinstance(data, list)
            assert all(isinstance(r, dict) and "code" in r and "kind" in r for r in data)
    finally:
        session.close()


def test_layout_rules_are_disabled_by_default(monkeypatch) -> None:
    session = SessionLocal()
    calls: list[str] = []
    try:
        mat_v = _get_version(session, "MAT10000")
        monkeypatch.setattr(
            "app.core.rules_engine.layout_checks.run",
            lambda path: calls.append(path) or [],
        )

        run_all(_parsed("Texte neutre."), _doc("fr"), session, [mat_v], src_path="sample.pdf")

        assert calls == []
    finally:
        session.close()


def test_layout_rules_require_explicit_opt_in(monkeypatch) -> None:
    session = SessionLocal()
    calls: list[str] = []
    try:
        mat_v = _get_version(session, "MAT10000")
        monkeypatch.setattr(
            "app.core.rules_engine.layout_checks.run",
            lambda path: calls.append(path) or [],
        )

        run_all(
            _parsed("Texte neutre."),
            _doc("fr"),
            session,
            [mat_v],
            src_path="sample.pdf",
            layout_enabled=True,
        )

        assert calls == ["sample.pdf"]
    finally:
        session.close()


def test_accent_fix_only_runs_for_explicit_french() -> None:
    session = SessionLocal()
    try:
        rule = Rule(
            name="Accents francais",
            kind="accent_fix",
            pattern=r"\bdeja\b",
            replacement="",
            severity="warning",
            message="Accent attendu",
            enabled=True,
            standard_version_id=None,
        )
        session.add(rule)
        session.flush()
        expected_code = f"CUSTOM_{rule.id.hex[:8].upper()}"
        parsed = _parsed("deja")

        missing_language = run_all(parsed, _doc(), session, None)
        english = run_all(parsed, _doc("en"), session, None)
        french = run_all(parsed, _doc("fr"), session, None)

        assert expected_code not in {item.rule_code for item in missing_language}
        assert expected_code not in {item.rule_code for item in english}
        assert expected_code in {item.rule_code for item in french}
    finally:
        session.rollback()
        session.close()


def test_mistral_read_timeout_is_retried_once(monkeypatch) -> None:
    session = SessionLocal()
    calls = 0

    class _Response:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return {"choices": [{"message": {"content": "{}"}}]}

    class _Client:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            pass

        def post(self, *_args: Any, **_kwargs: Any) -> _Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ReadTimeout("temporary timeout")
            return _Response()

    try:
        monkeypatch.setattr(llm_suggester, "get_llm_enabled", lambda _db: True)
        monkeypatch.setattr(
            llm_suggester,
            "get_effective",
            lambda _db: {
                "api_key": "test-key",
                "chat_model": "test-model",
                "base_url": "https://example.invalid",
            },
        )
        monkeypatch.setattr(llm_suggester.httpx, "Client", _Client)

        assert llm_suggester.call_chat(session, "system", "user") == "{}"
        assert calls == 2
    finally:
        session.close()


def test_ai_scan_continues_after_failed_page_group(monkeypatch) -> None:
    session = SessionLocal()
    pages = [
        ParsedPage(page=1, text="First page", spans=[]),
        ParsedPage(page=2, text="Second page", spans=[]),
    ]
    parsed = ParsedPdf(page_count=2, pages=pages, full_text="First page\nSecond page", is_signed=False)
    warnings: list[str] = []
    calls = 0

    def _scan(*_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise AppError("LLM_REPHRASE_FAILED", "ReadTimeout", status_code=502)
        return [{"original": "Second page", "proposed": "Rewritten page", "message": "Issue"}]

    try:
        monkeypatch.setattr(rules_engine, "get_ai_custom_prompt", lambda _db: "Check the document")
        monkeypatch.setattr(rules_engine, "_group_pages_by_text_budget", lambda *_args: [[pages[0]], [pages[1]]])
        monkeypatch.setattr(rules_engine, "scan_with_prompt", _scan)

        results = rules_engine._run_ai_custom(parsed, session, [], [], warnings=warnings)

        assert calls == 2
        assert [item.page for item in results] == [2]
        assert warnings == ["Scan checklist/IA partiellement indisponible (LLM_REPHRASE_FAILED) : ReadTimeout"]
    finally:
        session.close()


def test_ai_scan_is_not_triggered_by_document_metadata(monkeypatch) -> None:
    session = SessionLocal()
    parsed = _parsed("A document page")
    calls = 0

    def _scan(*_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return []

    try:
        monkeypatch.setattr(rules_engine, "get_ai_custom_prompt", lambda _db: "")
        monkeypatch.setattr(rules_engine, "scan_with_prompt", _scan)

        results = rules_engine._run_ai_custom(
            parsed,
            session,
            [],
            [],
            document=_doc("en"),
        )

        assert results == []
        assert calls == 0
    finally:
        session.close()
