from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.checks.standards import ste100
from app.core import docx_pipeline
from app.core.compiled_rule_executor import execute_pdf_rules
from app.core.rules_engine import run_all
from app.db.models import Standard
from app.db.session import SessionLocal
from app.parsers.docx_parser import Block, ParsedDocx
from app.parsers.pdf_parser import ParsedPage, ParsedPdf

_RULES = {rule.id: rule for rule in ste100.CATALOG["issue 7"]}


def _rule_status(rule_code: str, text: str) -> str:
    page = ParsedPage(page=1, text=text, spans=[])
    parsed = ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)
    results, _ = execute_pdf_rules(parsed, [_RULES[rule_code]])
    return results[0].status


def test_passive_voice_rejects_stative_adjectives_but_keeps_participles() -> None:
    assert _rule_status("STE_PASSIVE_VOICE", "The cover is red, green, or open.") == "PASS"
    assert _rule_status("STE_PASSIVE_VOICE", "The cover is inspected by the technician.") == "FAIL"
    assert _rule_status("STE_PASSIVE_VOICE", "The cover must be removed before inspection.") == "FAIL"


def test_first_person_does_not_flag_io_or_a_lowercase_variable() -> None:
    assert _rule_status("STE_FIRST_PERSON", "Connect the I/O cable. Set i = 0.") == "PASS"
    assert _rule_status("STE_FIRST_PERSON", "I will connect the cable.") == "FAIL"


def test_contractions_include_apostrophe_variants_without_flagging_possessives() -> None:
    assert _rule_status("STE_NO_CONTRACTION", "I'm ready; we won't proceed.") == "FAIL"
    assert _rule_status("STE_NO_CONTRACTION", "It\u2019s working.") == "FAIL"
    assert _rule_status("STE_NO_CONTRACTION", "The panel's cover is secure.") == "PASS"


def test_procedural_gerund_matches_after_a_line_break() -> None:
    assert _rule_status(
        "STE_PROCEDURAL_GERUND",
        "Before opening the panel, disconnect the power.",
    ) == "FAIL"
    assert _rule_status(
        "STE_PROCEDURAL_GERUND",
        "Introduction\nBefore opening the panel, disconnect the power.",
    ) == "FAIL"


def _ste100_version(session):
    standard = session.scalar(select(Standard).where(Standard.code == "ASD-STE100"))
    assert standard is not None
    version = standard.versions[0]
    version.disabled_rule_codes = "[]"
    return version


def _run_pdf(
    text: str,
    document_language: str | None,
    version,
    warnings: list[str],
    session,
):
    page = ParsedPage(page=1, text=text, spans=[])
    parsed = ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)
    document = SimpleNamespace(
        target_unit_system="none",
        document_language=document_language,
    )
    return run_all(
        parsed,
        document,
        session,
        [version],
        checklist_enabled=False,
        warnings=warnings,
    )


def _run_docx(text: str, document_language: str | None, version, warnings: list[str]):
    block = Block(target_id="dp1", index=1, zone="body", kind="paragraph", text=text)
    parsed = ParsedDocx(
        block_count=1,
        blocks=[block],
        headers=[],
        footers=[],
        full_text=text,
    )
    document = SimpleNamespace(
        target_unit_system="none",
        document_language=document_language,
    )
    session = SessionLocal()
    try:
        return docx_pipeline.run_docx(
            parsed,
            document,
            session,
            [version],
            checklist_enabled=False,
            warnings=warnings,
        )
    finally:
        session.close()


@pytest.mark.parametrize("document_language", ["fr", None])
@pytest.mark.parametrize("format_name", ["pdf", "docx"])
def test_ste100_is_skipped_unless_document_language_is_explicitly_english(
    document_language: str | None,
    format_name: str,
) -> None:
    text = "Use the tool only after you utilize the approved equipment."
    warnings: list[str] = []
    session = SessionLocal()
    try:
        version = _ste100_version(session)
        if format_name == "pdf":
            suggestions = _run_pdf(text, document_language, version, warnings, session)
        else:
            suggestions = _run_docx(text, document_language, version, warnings)
    finally:
        session.close()

    assert not any(s.rule_code.startswith("STE_") for s in suggestions)
    assert any("ASD-STE100" in warning for warning in warnings)


@pytest.mark.parametrize("format_name", ["pdf", "docx"])
def test_ste100_runs_for_explicitly_english_documents(format_name: str) -> None:
    text = "Use the tool only after you utilize the approved equipment."
    warnings: list[str] = []
    session = SessionLocal()
    try:
        version = _ste100_version(session)
        if format_name == "pdf":
            suggestions = _run_pdf(text, "en", version, warnings, session)
        else:
            suggestions = _run_docx(text, "en", version, warnings)
    finally:
        session.close()

    assert any(s.rule_code == "STE_VOCAB_NON_APPROVED" for s in suggestions)
    assert not any("ASD-STE100" in warning for warning in warnings)


@pytest.mark.parametrize("format_name", ["pdf", "docx"])
def test_long_sentence_rule_uses_the_sentence_length_detector(format_name: str) -> None:
    text = (
        "1. Remove the access panel and disconnect the electrical connector before "
        "you inspect the housing for damage or contamination in the maintenance area."
    )
    warnings: list[str] = []
    session = SessionLocal()
    try:
        version = _ste100_version(session)
        if format_name == "pdf":
            suggestions = _run_pdf(text, "en", version, warnings, session)
        else:
            suggestions = _run_docx(text, "en", version, warnings)
    finally:
        session.close()

    assert any(s.rule_code == "STE_LONG_SENTENCE" for s in suggestions)
