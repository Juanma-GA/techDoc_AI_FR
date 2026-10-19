import re

from app.checks.client_registry import load_active_client_configuration
from app.core.compiled_rule_runtime import _TextTarget, scope_targets
from app.parsers.pdf_parser import ParsedPage, Span


def test_demo_highlights_ata_rule_checks_number_after_marker_outside_footer() -> None:
    configuration = load_active_client_configuration(
        environ={"CLIENT_BUNDLE": "demo_rules"}
    )
    definition = next(
        rule
        for rule in configuration.bundle.rules
        if rule.code == "CUSTOM_HIGHLIGHTS_ATA_NUMBER"
    )
    check = definition.compiled_rule.checks[0]
    assert check.expected is not None
    assert definition.compiled_rule.target.page_type == "HIGHLIGHTS_PAGE_1"
    assert definition.compiled_rule.target.region == "page_without_footer"
    assert check.missing_anchor == r"(?i)\bATA\s+No\b"
    assert check.missing_anchor_position == "same"

    pattern = re.compile(str(check.expected).replace("{{meta_cmm_number}}", "80-80-01"))
    assert pattern.search("ATA No 80-80-01")
    assert pattern.search("80-80-01") is None
    assert pattern.search("ATA No 80-80-02") is None

    spans = [
        Span("Manual title", (10, 40, 90, 60), 1, "Arial", 10),
        Span("ATA No", (10, 300, 45, 320), 1, "Arial", 10),
        Span("80-80-01", (50, 300, 100, 320), 1, "Arial", 10),
        Span("80-80-01", (10, 920, 60, 940), 1, "Arial", 8),
    ]
    parsed_page = ParsedPage(
        page=1,
        text="Manual title ATA No 80-80-01 80-80-01",
        spans=spans,
        page_height=1000,
        page_type="HIGHLIGHTS_PAGE_1",
    )
    target = _TextTarget(
        page="1",
        text=parsed_page.text,
        raw_page=1,
        page_type="HIGHLIGHTS_PAGE_1",
    )
    scoped = scope_targets(
        definition.compiled_rule.target,
        [target],
        is_docx=False,
        blocks=None,
        pdf_pages=[parsed_page],
    )

    assert scoped is not None
    assert scoped[0].text.count("80-80-01") == 1
    assert "ATA No 80-80-01" in scoped[0].text
