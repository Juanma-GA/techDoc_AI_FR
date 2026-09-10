"""Deterministic CompiledRule execution tests on synthetic document structures."""

import json
from types import SimpleNamespace

from structlog.testing import capture_logs

from app.core.compiled_rule_executor import execute_docx_rules, execute_pdf_rules
from app.core.compiled_rules import Check, CompiledRule, Condition, FieldRef, RuleTarget
from app.core.logging import configure_logging
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


def test_pdf_semantic_rule_receives_current_document_metadata(monkeypatch) -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="The procedure is complete.")],
        full_text="The procedure is complete.",
        is_signed=False,
    )
    rule = CompiledRule(
        id="CHECKLIST_SEMANTIC_META",
        topic="Revision consistency",
        execution="semantic",
        target=RuleTarget(page="all", region="full_page"),
        semantic_instruction="Check the document revision context.",
        source="user_checklist",
    )
    captured: dict[str, object] = {}

    def _chat(_db, _system, user, **_kwargs):
        captured.update(json.loads(user))
        return json.dumps({"violations": []})

    monkeypatch.setattr("app.core.compiled_rule_executor.call_chat", _chat)

    results, raws = execute_pdf_rules(
        parsed,
        [rule],
        db=object(),
        document=SimpleNamespace(
            meta_revision_date="JUL 27/26",
            meta_cmm_number="79-30-02",
            document_language="en",
        ),
    )

    assert results[0].status == "PASS"
    assert raws == []
    assert captured["document_metadata"] == {
        "meta_revision_date": "JUL 27/26",
        "meta_cmm_number": "79-30-02",
        "document_language": "en",
    }


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


def test_contains_none_forbidden_terms_are_flagged_with_replacement() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="Use the obsolete part immediately.")],
        full_text="Use the obsolete part immediately.",
        is_signed=False,
    )
    rule = _rule(
        Check(
            field="text",
            operator="contains_none",
            expected=["obsolete", "deprecated"],
            replacements={"obsolete": "legacy"},
        )
    )

    results, raws = execute_pdf_rules(parsed, [rule])

    assert results[0].status == "FAIL"
    assert raws[0].original == "obsolete"
    assert raws[0].proposed == "legacy"


def test_contains_any_passes_when_one_synonym_is_present() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="Torque to 50 Nm.")],
        full_text="Torque to 50 Nm.",
        is_signed=False,
    )
    rule = _rule(Check(field="text", operator="contains_any", expected=["Nm", "lbf-in"]))

    results, raws = execute_pdf_rules(parsed, [rule])

    assert results[0].status == "PASS"
    assert raws == []


def test_contains_all_fails_when_one_mandatory_mention_is_missing() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="Warning: wear gloves.")],
        full_text="Warning: wear gloves.",
        is_signed=False,
    )
    rule = _rule(Check(field="text", operator="contains_all", expected=["Warning", "wear goggles"]))

    results, _raws = execute_pdf_rules(parsed, [rule])

    assert results[0].status == "FAIL"


def _copyright_page() -> ParsedPdf:
    return ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text="Title block header. © 2000-2026 Example Corp.",
                spans=[
                    Span(text="Title block header.", bbox=(10.0, 10.0, 200.0, 30.0), page=1, font="Arial", size=10.0),
                    Span(
                        text="© 2000-2026 Example Corp.",
                        bbox=(10.0, 770.0, 300.0, 790.0),
                        page=1,
                        font="Arial",
                        size=8.0,
                    ),
                ],
            )
        ],
        full_text="Title block header. © 2000-2026 Example Corp.",
        is_signed=False,
    )


def _copyright_year_rule() -> CompiledRule:
    return CompiledRule(
        id="CHECKLIST_COPYRIGHT_YEAR",
        topic="Copyright year matches revision year",
        execution="deterministic",
        target=RuleTarget(page="1", region="footer"),
        checks=[
            Check(
                field="copyright_end_year",
                operator="equals_field",
                compare_to=FieldRef(
                    source="document_meta",
                    field="meta_revision_date",
                    normalization=["extract_year"],
                ),
            )
        ],
        source="user_checklist",
    )


def test_equals_field_passes_when_copyright_year_matches_revision_year() -> None:
    document = SimpleNamespace(meta_revision_date="MAR 18/26")

    results, raws = execute_pdf_rules(_copyright_page(), [_copyright_year_rule()], document=document)

    assert results[0].status == "PASS"
    assert raws == []


def test_equals_field_fails_when_copyright_year_does_not_match_revision_year() -> None:
    document = SimpleNamespace(meta_revision_date="MAR 18/25")

    results, raws = execute_pdf_rules(_copyright_page(), [_copyright_year_rule()], document=document)

    assert results[0].status == "FAIL"
    assert results[0].evidence is not None
    assert results[0].evidence.observed_value == "2026"
    assert results[0].evidence.expected_value == "2025"


def test_equals_field_is_inconclusive_when_document_meta_is_missing() -> None:
    document = SimpleNamespace(meta_revision_date=None)

    results, _raws = execute_pdf_rules(_copyright_page(), [_copyright_year_rule()], document=document)

    assert results[0].status == "INCONCLUSIVE"


def test_missing_document_meta_does_not_use_checklist_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.mistral_settings.get_checklist_context",
        lambda _db: {"meta_revision_date": "MAR 18/25"},
    )

    results, raws = execute_pdf_rules(
        _copyright_page(),
        [_copyright_year_rule()],
        db=object(),
        document=SimpleNamespace(meta_revision_date=None),
    )

    assert results[0].status == "INCONCLUSIVE"
    assert raws == []


def test_missing_required_pattern_does_not_create_a_regex_patch() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="No copyright notice on this page.")],
        full_text="No copyright notice on this page.",
        is_signed=False,
    )
    rule = _rule(Check(field="text", operator="regex_exists", expected=r"©\s*2000-(\d{4})"))

    results, raws = execute_pdf_rules(parsed, [rule])

    assert results[0].status == "FAIL"
    assert raws == []


def test_only_if_skips_rule_when_condition_is_not_met() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="No CMM reference here.")],
        full_text="No CMM reference here.",
        is_signed=False,
    )
    rule = CompiledRule(
        id="CHECKLIST_CMM",
        topic="CMM footer mention",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[Check(field="text", operator="exists", expected="CMM")],
        source="user_checklist",
        only_if=Condition(field="meta_cmm_number", state="present"),
    )
    document = SimpleNamespace(meta_cmm_number=None)

    results, raws = execute_pdf_rules(parsed, [rule], document=document)

    assert results == []
    assert raws == []


def test_regex_exists_passes_when_mandatory_pattern_with_variable_year_is_present() -> None:
    """Reproduces the reported bug: a mandatory copyright text with a
    variable year must NOT be flagged just because the (correct) text is
    present. `regex` (forbidden-pattern) would wrongly FAIL here; the
    mirror `regex_exists` (mandatory-pattern) must PASS."""
    rule = _rule(Check(field="text", operator="regex_exists", expected=r"©\s*2000-(\d{4})"))

    results, raws = execute_pdf_rules(_copyright_page(), [rule])

    assert results[0].status == "PASS"
    assert raws == []


def test_regex_exists_fails_when_mandatory_pattern_is_absent() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="No copyright notice on this page.")],
        full_text="No copyright notice on this page.",
        is_signed=False,
    )
    rule = _rule(Check(field="text", operator="regex_exists", expected=r"©\s*2000-(\d{4})"))

    results, _raws = execute_pdf_rules(parsed, [rule])

    assert results[0].status == "FAIL"


def test_regex_forbidden_pattern_still_fails_when_found_unlike_regex_exists() -> None:
    """`regex` keeps its original "flag if found" semantics — only
    `regex_exists` is the mirror mandatory-pattern operator."""
    rule = _rule(Check(field="text", operator="regex", expected=r"©\s*2000-(\d{4})"))

    results, _raws = execute_pdf_rules(_copyright_page(), [rule])

    assert results[0].status == "FAIL"


def test_all_compiled_checks_are_evaluated_after_first_failure() -> None:
    parsed = _copyright_page()
    rule = CompiledRule(
        id="CHECKLIST_ALL_CHECKS",
        topic="Copyright checks",
        execution="deterministic",
        target=RuleTarget(page="all", region="full_page"),
        checks=[
            Check(field="text", operator="regex_exists", expected=r"Missing marker"),
            Check(
                field="copyright_end_year",
                operator="equals_field",
                compare_to=FieldRef(
                    source="document_meta",
                    field="meta_revision_date",
                    normalization=["extract_year"],
                ),
            ),
        ],
        source="user_checklist",
    )

    configure_logging("INFO")
    try:
        with capture_logs() as logs:
            results, _raws = execute_pdf_rules(
                parsed,
                [rule],
                document=SimpleNamespace(meta_revision_date="MAR 18/26"),
            )
    finally:
        configure_logging("WARNING")

    check_logs = [
        entry for entry in logs
        if entry.get("event") == "compiled_check_evaluated"
        and entry.get("rule_id") == "CHECKLIST_ALL_CHECKS"
    ]
    assert [entry["check_index"] for entry in check_logs] == [0, 1]
    assert [entry["status"] for entry in check_logs] == ["FAIL", "PASS"]
    assert results[0].status == "FAIL"


def test_regex_exists_resolves_document_context_placeholder() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text="Revision: Rev. 01",
                spans=[Span(text="Revision: Rev. 01", bbox=(10.0, 10.0, 150.0, 25.0), page=1, font="Arial", size=10.0)],
            )
        ],
        full_text="Revision: Rev. 01",
        is_signed=False,
    )
    rule = _rule(
        Check(
            field="text",
            operator="regex_exists",
            expected=r"Revision\s*:\s*{{meta_revision_number}}",
        )
    )

    results, _raws = execute_pdf_rules(
        parsed,
        [rule],
        document=SimpleNamespace(meta_revision_number="Rev. 01"),
    )

    assert results[0].status == "PASS"
    assert results[0].evidence is not None
    assert results[0].evidence.expected_value == r"Revision\s*:\s*{{meta_revision_number}}"


def test_regex_context_placeholder_is_inconclusive_when_value_is_missing() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="Revision: unknown")],
        full_text="Revision: unknown",
        is_signed=False,
    )
    rule = _rule(
        Check(field="text", operator="regex_exists", expected=r"{{meta_revision_number}}")
    )

    results, raws = execute_pdf_rules(
        parsed,
        [rule],
        document=SimpleNamespace(meta_revision_number=None),
    )

    assert results[0].status == "INCONCLUSIVE"
    assert raws == []


def test_copyright_year_mismatch_only_flags_the_year_not_the_whole_block() -> None:
    """The narrow fix: when the copyright year is wrong, the correction
    targets just the 4-digit year, not the whole legal disclaimer."""
    document = SimpleNamespace(meta_revision_date="MAR 18/25")

    results, raws = execute_pdf_rules(_copyright_page(), [_copyright_year_rule()], document=document)

    assert results[0].status == "FAIL"
    assert len(raws) == 1
    assert raws[0].original == "2026"
    assert raws[0].proposed == "2025"


def test_regex_evaluates_every_page_and_logs_document_context() -> None:
    parsed = ParsedPdf(
        page_count=2,
        pages=[
            ParsedPage(
                page=1,
                text="TODO on the first page.",
                spans=[Span(text="TODO", bbox=(10.0, 10.0, 40.0, 20.0), page=1, font="Arial", size=10.0)],
            ),
            ParsedPage(
                page=2,
                text="TODO on the second page.",
                spans=[Span(text="TODO", bbox=(20.0, 30.0, 50.0, 40.0), page=2, font="Arial", size=10.0)],
            ),
        ],
        full_text="TODO on the first page.\nTODO on the second page.",
        is_signed=False,
    )
    document = SimpleNamespace(
        meta_revision_date="JUL 27/26",
        meta_cmm_number="79-30-02",
    )

    configure_logging("INFO")
    try:
        with capture_logs() as logs:
            results, _raws = execute_pdf_rules(
                parsed,
                [_rule(Check(field="text", operator="regex", expected=r"\bTODO\b"))],
                document=document,
            )
    finally:
        configure_logging("WARNING")

    regex_logs = [entry for entry in logs if entry.get("event") == "compiled_regex_evaluated"]
    assert [entry["page"] for entry in regex_logs] == ["1", "2"]
    assert regex_logs[0]["match_count"] == 1
    assert regex_logs[0]["document_metadata"] == {
        "meta_revision_date": "JUL 27/26",
        "meta_cmm_number": "79-30-02",
    }
    assert results[0].status == "FAIL"
    assert results[0].evidence is not None
    assert results[0].evidence.page == "1"


def test_regex_evidence_uses_all_spans_for_a_recomposed_region() -> None:
    parsed = ParsedPdf(
        page_count=1,
        pages=[
            ParsedPage(
                page=1,
                text="Forbidden term",
                spans=[
                    Span(text="Forbidden", bbox=(10.0, 10.0, 70.0, 20.0), page=1, font="Arial", size=10.0),
                    Span(text="term", bbox=(80.0, 10.0, 120.0, 20.0), page=1, font="Arial", size=10.0),
                ],
            )
        ],
        full_text="Forbidden term",
        is_signed=False,
    )
    rule = _rule(
        Check(field="text", operator="regex", expected=r"Forbidden term"),
        region="header",
    )

    results, _raws = execute_pdf_rules(parsed, [rule])

    assert results[0].status == "FAIL"
    assert results[0].evidence is not None
    assert results[0].evidence.location.bbox == (10.0, 10.0, 120.0, 20.0)
