"""STE_LONG_SENTENCE : le détecteur de phrase longue (kind sentence_length)
remplace l'ancienne sentinelle regex qui ne matchait jamais rien."""

from __future__ import annotations

from app.checks import catalog_runner, style_checks
from app.parsers.pdf_parser import ParsedPage, ParsedPdf

_LONG = (
    "When the operator wants to remove the panel he must first ensure that the "
    "equipment is fully de-energised and then he must use the dedicated tool "
    "provided inside the maintenance kit before continuing."
)  # > 20 mots
_SHORT = "Remove the panel."


def _page(text: str) -> ParsedPage:
    return ParsedPage(page=1, text=text, spans=[], has_text_layer=True)


def test_style_checks_flags_long_sentence() -> None:
    rule = {"code": "STE_LONG_SENTENCE", "severity": "warning", "pattern": "20"}
    out = style_checks.run([_page(_LONG)], rule)
    assert len(out) == 1
    assert out[0].rule_code == "STE_LONG_SENTENCE"
    assert out[0].rule_kind == "standard"


def test_style_checks_ignores_short_sentence() -> None:
    rule = {"code": "STE_LONG_SENTENCE", "severity": "warning", "pattern": "20"}
    assert style_checks.run([_page(_SHORT)], rule) == []


def test_style_checks_uses_descriptive_limit_above_procedural_limit() -> None:
    text = (
        "The operator can remove the panel after the equipment has been fully "
        "de-energised and the maintenance kit is available for the inspection."
    )
    rule = {
        "code": "STE_LONG_SENTENCE",
        "severity": "warning",
        "pattern": "20",
        "descriptive_max_words": 25,
    }

    assert style_checks.run([_page(text)], rule) == []


def test_style_checks_applies_procedural_limit_to_numbered_steps() -> None:
    text = (
        "1. Remove the access panel and disconnect the electrical connector before "
        "you inspect the housing for damage or contamination in the maintenance area."
    )
    rule = {
        "code": "STE_LONG_SENTENCE",
        "severity": "warning",
        "pattern": "20",
        "descriptive_max_words": 25,
    }

    out = style_checks.run([_page(text)], rule)

    assert len(out) == 1
    assert out[0].original == text


def test_style_checks_splits_sentences_when_next_sentence_starts_lowercase() -> None:
    text = (
        "The technician must inspect the panel and verify that the equipment is stable "
        "before the test begins. then the operator must record the result and confirm "
        "that all fasteners remain in the correct position."
    )
    rule = {
        "code": "STE_LONG_SENTENCE",
        "severity": "warning",
        "pattern": "20",
        "descriptive_max_words": 25,
    }

    assert style_checks.run([_page(text)], rule) == []


def test_catalog_runner_dispatches_sentence_length() -> None:
    parsed = ParsedPdf(page_count=1, pages=[_page(_LONG)], full_text=_LONG, is_signed=False)
    catalog = [
        {"code": "STE_LONG_SENTENCE", "kind": "sentence_length", "severity": "warning", "pattern": "20"}
    ]
    out = catalog_runner.run(parsed, catalog)
    assert any(r.rule_code == "STE_LONG_SENTENCE" for r in out)
