"""Deterministic CompiledRule execution tests on synthetic document structures."""

import json

from app.core.compiled_rule_executor import execute_docx_rules, execute_pdf_rules
from app.core.compiled_rules import Check, CompiledRule, RuleTarget
from app.parsers.docx_parser import Block
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, Span


def _rule(check: Check, *, region: str = "full_page") -> CompiledRule:
    return CompiledRule(
        id="CHECKLIST_TEST",
        topic="Synthetic test",
        execution="deterministic",
        target=RuleTarget(page="all", region=region),
        checks=[check],
        source="user_checklist",
        origin_ref="synthetic.xlsx:Review:2",
    )


def test_pdf_regex_violation_has_bbox_evidence() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text="Remove the TODO marker.",
                spans=[Span(text="TODO", bbox=(10.0, 20.0, 30.0, 40.0), page=1, font="Arial", size=10.0)],
            )
        ],
        full_text="Remove the TODO marker.",
        is_signed=False,
    )

    results, raws = execute_pdf_rules(parsed, [_rule(Check(field="text", operator="regex", expected=r"\bTODO\b"))])

    assert results[0].status == "FAIL"
    assert results[0].evidence is not None
    assert results[0].evidence.location.type == "bbox"
    assert results[0].evidence.location.bbox == (10.0, 20.0, 30.0, 40.0)
    assert raws[0].rule_code == "CHECKLIST_TEST"


def test_docx_normalized_equals_has_target_evidence() -> None:
    blocks = [Block(target_id="dp4", index=4, zone="header", kind="paragraph", text="Revision number:  REV  02 ", page=1)]
    rule = _rule(
        Check(
            field="revision_number",
            operator="normalized_equals",
            expected="REV 02",
            normalization=["unicode", "trim", "spaces"],
        ),
        region="header",
    )

    results, raws = execute_docx_rules(blocks, [rule])

    assert results[0].status == "PASS"
    assert results[0].evidence is not None
    assert results[0].evidence.location.type == "target_id"
    assert results[0].evidence.location.target_id == "dp4"
    assert raws == []


def test_pdf_geometric_region_is_inconclusive() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="REV 01")],
        full_text="REV 01",
        is_signed=False,
    )
    results, raws = execute_pdf_rules(
        parsed,
        [_rule(Check(field="revision_number", operator="equals", expected="REV 02"), region="header")],
    )

    assert results[0].status == "INCONCLUSIVE"
    assert raws == []


def test_pdf_semantic_violation_emits_exact_comment(monkeypatch) -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text="The technician may continue without recording the torque value.",
                spans=[
                    Span(
                        text="may continue",
                        bbox=(10.0, 20.0, 90.0, 40.0),
                        page=1,
                        font="Arial",
                        size=10.0,
                    )
                ],
            )
        ],
        full_text="The technician may continue without recording the torque value.",
        is_signed=False,
    )
    rule = CompiledRule(
        id="CHECKLIST_SEMANTIC",
        topic="Modal verb usage",
        execution="semantic",
        target=RuleTarget(page="all", region="full_page"),
        semantic_instruction="La procédure ne doit pas autoriser une action sans enregistrement du couple.",
        source="user_checklist",
    )

    monkeypatch.setattr(
        "app.core.compiled_rule_executor.call_chat",
        lambda *_args, **_kwargs: json.dumps(
            {
                "violations": [
                    {
                        "page": "1",
                        "original": "may continue",
                        "proposed": "must record the torque value before continuing",
                        "message": "The procedure permits continuing without the required record.",
                    }
                ]
            }
        ),
    )

    results, raws = execute_pdf_rules(parsed, [rule], db=object())

    assert results[0].status == "FAIL"
    assert len(raws) == 1
    assert raws[0].original == "may continue"
    assert raws[0].proposed.startswith("must record")
    assert raws[0].page == 1


def test_active_manual_rule_emits_user_review_comment() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="Visual content")],
        full_text="Visual content",
        is_signed=False,
    )
    rule = CompiledRule(
        id="CHECKLIST_MANUAL",
        topic="Logo placement",
        execution="manual",
        target=RuleTarget(page="all", region="full_page"),
        manual_instruction="Verify the logo placement visually.",
        source="user_checklist",
    )

    results, raws = execute_pdf_rules(parsed, [rule])

    assert results[0].status == "MANUAL"
    assert len(raws) == 1
    assert "logo placement" in raws[0].message
