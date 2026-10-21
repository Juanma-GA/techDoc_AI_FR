from __future__ import annotations

from types import SimpleNamespace

from app.checks.thales_rules.preparation_detector import detect_pages_to_modify
from app.core.compiled_rules import RuleTarget
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def test_page_decision_includes_successful_rule_results(monkeypatch) -> None:
    rule = SimpleNamespace(
        id="TP1-CHECK",
        topic="TP1 title check",
        target=RuleTarget(page="all", region="full_page", page_type="TP1"),
        failure_message=None,
        source_instruction=None,
    )
    bundle = SimpleNamespace(
        page_classifier=None,
        operations={},
        mapping=SimpleNamespace(entities={}),
    )
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="TP1", page_type="TP1")],
        full_text="TP1",
        is_signed=False,
    )
    monkeypatch.setattr(
        "app.checks.thales_rules.preparation_detector.execute_pdf_rules",
        lambda *_args, **_kwargs: ([SimpleNamespace(rule_id="TP1-CHECK", status="PASS")], []),
    )
    monkeypatch.setattr(
        "app.checks.thales_rules.preparation_detector.map_preparation_pages_to_toc",
        lambda *_args, **_kwargs: None,
    )

    decisions = detect_pages_to_modify(parsed, SimpleNamespace(), [rule], None, bundle)

    assert decisions[0]["rule_results"] == [
        {
            "rule_id": "TP1-CHECK",
            "title": "TP1 title check",
            "message": "TP1 title check",
            "status": "PASS",
        }
    ]


def test_ocr_page_font_size_failure_is_inconclusive_without_font_metadata(monkeypatch) -> None:
    rule = SimpleNamespace(
        id="TP1-FONT",
        topic="TP1 font size",
        target=RuleTarget(page="all", region="full_page", page_type="TP1"),
        failure_message=None,
        source_instruction=None,
        checks=[SimpleNamespace(operator="font_size_equals")],
    )
    bundle = SimpleNamespace(
        page_classifier=None,
        operations={},
        mapping=SimpleNamespace(entities={}),
    )
    parsed = ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text="TP1",
                has_text_layer=False,
                page_type="TP1",
            )
        ],
        full_text="TP1",
        is_signed=False,
    )
    monkeypatch.setattr(
        "app.checks.thales_rules.preparation_detector.execute_pdf_rules",
        lambda *_args, **_kwargs: ([SimpleNamespace(rule_id="TP1-FONT", status="FAIL")], []),
    )
    monkeypatch.setattr(
        "app.checks.thales_rules.preparation_detector.map_preparation_pages_to_toc",
        lambda *_args, **_kwargs: None,
    )

    decisions = detect_pages_to_modify(parsed, SimpleNamespace(), [rule], None, bundle)

    assert decisions[0]["is_modified"] is None
    assert decisions[0]["decision_status"] == "needs_review"
    assert decisions[0]["rule_results"][0]["status"] == "INCONCLUSIVE"
