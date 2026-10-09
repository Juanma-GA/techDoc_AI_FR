from __future__ import annotations

from app.checks.thales_rules.rules import (
    CUSTOM_BAR_PSI_CONVERSION,
    CUSTOM_CMM_NUMBER,
    CUSTOM_CMM_NUMBER_FONT_SIZE,
    CUSTOM_COPYRIGHT_POSITION,
    CUSTOM_DECIMAL_COMMA,
    CUSTOM_ENUMERATION_PUNCTUATION_SWAP,
    CUSTOM_FOOTER_PAGE_NUMBER,
    CUSTOM_HEADER_DOCUMENT_TYPE,
    CUSTOM_FORBIDDEN_CONSUMABLES,
    CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE,
    CUSTOM_HIGHLIGHTS_HOLDER,
    CUSTOM_HIGHLIGHTS_LEGEND_FOOTER,
    CUSTOM_HIGHLIGHTS_ATA_NUMBER,
    CUSTOM_HIGHLIGHTS_PNR_HEADER,
    CUSTOM_HIGHLIGHTS_REVISION_HEADER,
    CUSTOM_METRIC_LENGTH_INCH_CONVERSION,
    CUSTOM_METRIC_MASS_LBF_CONVERSION,
    CUSTOM_METRIC_TORQUE_LBF_IN_CONVERSION,
    CUSTOM_NO_DEGREE_C_SYMBOL,
    CUSTOM_NO_DEGREE_F_SYMBOL,
    CUSTOM_PASCAL_INHG_CONVERSION,
    CUSTOM_PARAGRAPH_JUSTIFICATION,
    CUSTOM_REPAIR_NOTE,
    CUSTOM_REPLACE_LEGACY_NAMES,
    CUSTOM_SENTENCE_PUNCTUATION,
    CUSTOM_STORAGE_NOTE,
    CUSTOM_THALES_LOGO_FONT_SIZE,
    CUSTOM_TEMPERATURE_FAHRENHEIT,
    CUSTOM_INTRODUCTION_SHOP_VERIFICATION,
    CUSTOM_TP1_THALES_LOGO_FONT_SIZE,
    CUSTOM_TP1_HEADER_DOCUMENT_TYPE,
    CUSTOM_TP1_THALES_ADDRESS,
    CUSTOM_TESTING_NOTE,
    CUSTOM_TP2_IMPORTANT_NOTICE,
    CUSTOM_TITLE_PAGE_COPYRIGHT,
    DOCUMENT_TYPE_PATTERN,
    DOCUMENT_TYPES,
    HIGHLIGHTS_DOCUMENT_TYPE_PATTERN,
)
from app.checks.thales_rules.operations import highlights_document_type_expected


def test_rule_factory_builds_compiled_rule_and_legacy_metadata() -> None:
    definition = CUSTOM_THALES_LOGO_FONT_SIZE

    assert definition.code == "CUSTOM_THALES_LOGO_FONT_SIZE"
    assert definition.compiled_rule.topic == "Taille du logo THALES sur les pages hors TP1"
    assert definition.compiled_rule.origin_ref == (
        "THALES-CUSTOM:v1:CUSTOM_THALES_LOGO_FONT_SIZE"
    )
    assert definition.metadata == {
        "description": (
            "Le T de la police Thales en debut de page doit avoir une taille "
            "de 31 pt hors pages TP1."
        ),
        "kind": "field_required",
        "severity": "warning",
        "message": "La taille du logo THALES hors TP1 n'est pas 31 pt.",
        "description_en": (
            "The Thales T at the start of the page must use a 31 pt font outside TP1 pages."
        ),
        "message_en": "The THALES logo size outside TP1 is not 31 pt.",
    }
    assert definition.compiled_rule.checks[0].operator == "font_size_equals"
    assert definition.compiled_rule.target.excluded_page_types == ["TP1"]


def test_cmm_font_size_rule_preserves_execution_and_presentation_severity() -> None:
    definition = CUSTOM_CMM_NUMBER_FONT_SIZE

    assert definition.compiled_rule.severity == "warning"
    assert definition.metadata["severity"] == "error"
    assert definition.compiled_rule.checks[0].expected == 23


def test_cmm_number_rule_keeps_mapping_pattern_and_first_issue_anchor() -> None:
    definition = CUSTOM_CMM_NUMBER
    check = definition.compiled_rule.checks[0]

    assert check.operator == "regex_exists"
    assert check.expected == r"(?<!\w){{meta_cmm_number}}(?!\w)"
    assert check.expected_display == "{{meta_cmm_number}}"
    assert check.missing_anchor == r"(?i)\bFirst\s+Issue\b"
    assert definition.compiled_rule.target.region == "footer"
    assert definition.metadata["severity"] == "error"


def test_tp1_logo_rule_uses_the_same_factory_and_metadata_contract() -> None:
    definition = CUSTOM_TP1_THALES_LOGO_FONT_SIZE

    assert definition.code == "CUSTOM_TP1_THALES_LOGO_FONT_SIZE"
    assert definition.compiled_rule.target.page_type == "TP1"
    assert definition.compiled_rule.checks[0].expected == 36
    assert definition.metadata["severity"] == "warning"
    assert definition.metadata["description_en"] == (
        "The Thales T at the start of a TP1 page must use a 36 pt font."
    )


def test_degree_symbol_rules_keep_their_replacements_and_translations() -> None:
    celsius = CUSTOM_NO_DEGREE_C_SYMBOL
    fahrenheit = CUSTOM_NO_DEGREE_F_SYMBOL

    assert celsius.compiled_rule.checks[0].replacement == "deg. C"
    assert celsius.metadata["description_en"] == "The °C symbol must be written as deg. C."
    assert fahrenheit.compiled_rule.checks[0].replacement == "deg. F"
    assert fahrenheit.metadata["message_en"] == "The °F symbol is forbidden: use deg. F."


def test_regex_replacement_rules_keep_patterns_and_messages() -> None:
    decimal_comma = CUSTOM_DECIMAL_COMMA.compiled_rule.checks[0]
    temperature = CUSTOM_TEMPERATURE_FAHRENHEIT.compiled_rule.checks[0]
    legacy_name = CUSTOM_REPLACE_LEGACY_NAMES.compiled_rule.checks[0]

    assert decimal_comma.expected == r"(?<!\d)(\d+),(\d+)(?!\d)"
    assert decimal_comma.replacement == r"\1.\2"
    assert temperature.replacement == "{{temperature_fahrenheit}}"
    assert legacy_name.replacement == "THALES"
    assert CUSTOM_TEMPERATURE_FAHRENHEIT.metadata["message_en"] == (
        "A temperature in deg. C must be followed by its conversion in deg. F."
    )


def test_forbidden_consumables_rule_keeps_terms_and_removal_proposal() -> None:
    check = CUSTOM_FORBIDDEN_CONSUMABLES.compiled_rule.checks[0]

    assert check.operator == "contains_none"
    assert check.expected == ["Silica gel", "dessicant bag"]
    assert check.replacement == ""


def test_title_copyright_rule_keeps_generic_cross_field_checks() -> None:
    definition = CUSTOM_TITLE_PAGE_COPYRIGHT
    checks = definition.compiled_rule.checks

    assert definition.compiled_rule.target.region == "footer"
    assert definition.compiled_rule.target.page_state == "modified"
    assert [check.operator for check in checks] == [
        "regex_exists",
        "equals_field",
        "equals_field",
    ]
    assert checks[2].compare_to is not None
    assert checks[2].compare_to.field == "meta_revision_date"
    assert checks[1].compare_to is not None
    assert checks[1].compare_to.field == "meta_first_issue_date"
    assert definition.metadata["description_en"].startswith(
        "The footer of pages modified by the revision"
    )


def test_copyright_position_rule_uses_all_pdf_pages() -> None:
    definition = CUSTOM_COPYRIGHT_POSITION
    check = definition.compiled_rule.checks[0]

    assert definition.compiled_rule.target.page == "all"
    assert definition.compiled_rule.target.region == "full_page"
    assert definition.compiled_rule.target.page_state is None
    assert check.operator == "client_operation"
    assert check.operation == "copyright_position"
    assert definition.compiled_rule.severity == "warning"


def test_tp2_important_notice_bundle_definition_keeps_text_and_normalization() -> None:
    definition = CUSTOM_TP2_IMPORTANT_NOTICE
    check = definition.compiled_rule.checks[0]

    assert definition.code == "CUSTOM_TP2_IMPORTANT_NOTICE"
    assert definition.compiled_rule.target.page_type == "TP2"
    assert check.operator == "normalized_equals"
    assert check.expected == (
        "IMPORTANT NOTICE\n"
        "This document and any information contained herein are the sole property "
        "of THALES AVS FRANCE SAS and have been disclosed under a License Agreement. "
        "They cannot be used, reproduced or disclosed without the prior express "
        "written approval of THALES AVS FRANCE SAS.\n"
        "In particular, they shall not be used in the creation, manufacture, "
        "development or derivation of any repairs, modifications, spare parts, "
        "design, or configuration changes or to obtain EASA, FAA or any other "
        "government or regulatory approval to do so.\n"
        "Should THALES AVS FRANCE SAS consent be given for reproduction in whole "
        "or in part, this notice and the notice set forth on each page of this "
        "document shall appear in any such reproduction in whole or in part.\n"
        "The recipient shall not use this document for any purpose other than the "
        "one stated in the relevant applicable License agreement under which it "
        "has been disclosed and it shall be returned to THALES AVS FRANCE SAS "
        "immediately upon request.\n"
        "TO BE CONSIDERED VALID FOR PART 145 REQUIREMENTS, ALL MAINTENANCE "
        "DOCUMENTATION HAS TO BE IDENTIFIED ON EACH PAGE WITH A WATERMARK "
        "AUTHORIZING ITS USE BY THE END USER COMPANY. SUCH WATERMARK MIGHT BE AS "
        "FOLLOWS:\n"
        "\u201cProvided to [USER_ID] for [COMPANY_NAME] only under license agreement "
        "[LICENSE_NUMBER] for year [YEAR] only\u201d\n"
        "Users are kindly requested to notify THALES AVS FRANCE SAS of any "
        "discrepancy, omission or error found in this manual.\n"
        "Please send your comments to:\n"
        "THALES AVS FRANCE SAS\n"
        "Technical Publications Department\n"
        "AGS, Campus Thales Bordeaux\n"
        "75-77 Avenue Marcel Dassault\n"
        "33700 Merignac\n"
        "France\n"
        "E-mail: techpubs.frontoffice@fr.thalesgroup.com\n"
        "If you do not yet have access to our website, you can apply through the "
        "following address:\n"
        "https://www.thalesgroup.com/customer-online"
    )
    assert check.normalization == ["unicode", "spaces", "line_breaks", "trim"]


def test_highlights_revision_header_keeps_target_anchor_and_single_suggestion() -> None:
    definition = CUSTOM_HIGHLIGHTS_REVISION_HEADER
    check = definition.compiled_rule.checks[0]

    assert definition.compiled_rule.target.page_types == [
        "HIGHLIGHTS",
        "HIGHLIGHTS_PAGE_1",
    ]
    assert check.suggestion_mode == "single"
    assert check.missing_anchor == r"(?i)\bHighlights\b"
    assert check.missing_anchor_position == "above"
    assert "{{meta_revision_number}}" in str(check.expected)
    assert "{{meta_revision_date}}" in str(check.expected)


def test_highlights_ata_rule_keeps_first_page_scope_and_single_anchor() -> None:
    definition = CUSTOM_HIGHLIGHTS_ATA_NUMBER
    check = definition.compiled_rule.checks[0]

    assert definition.compiled_rule.target.page_type == "HIGHLIGHTS_PAGE_1"
    assert definition.compiled_rule.only_if is not None
    assert definition.compiled_rule.only_if.field == "meta_cmm_number"
    assert check.suggestion_mode == "single"
    assert check.missing_anchor == r"(?i)\bATA\s+No\b"


def test_highlights_pnr_header_rule_keeps_header_scope_and_all_suggestions() -> None:
    definition = CUSTOM_HIGHLIGHTS_PNR_HEADER
    check = definition.compiled_rule.checks[0]

    assert definition.compiled_rule.target.region == "header"
    assert definition.compiled_rule.target.page_types == [
        "HIGHLIGHTS",
        "HIGHLIGHTS_PAGE_1",
    ]
    assert definition.compiled_rule.only_if is not None
    assert definition.compiled_rule.only_if.field == "meta_pnr_number"
    assert check.operator == "client_operation"
    assert check.operation == "document_structure"
    assert check.operation_params == {"control": "highlights_pnr_header"}


def test_document_type_rules_use_bundle_patterns_and_preserve_scopes() -> None:
    header = CUSTOM_HEADER_DOCUMENT_TYPE.compiled_rule
    tp1 = CUSTOM_TP1_HEADER_DOCUMENT_TYPE.compiled_rule

    assert DOCUMENT_TYPES == [
        "OVERHAUL MANUAL",
        "COMPONENT MAINTENANCE MANUAL",
        "MAINTENANCE MANUAL",
        "ABBREVIATED COMPONENT MAINTENANCE MANUAL",
        "OPERATING MANUAL",
        "ILLUSTRATED PARTS CATALOG",
        "COMPONENT MAINTENANCE PARTS LIST",
        "OPERATING MANUAL PARTS LIST",
    ]
    for document_type in DOCUMENT_TYPES:
        assert highlights_document_type_expected(document_type) == document_type
    assert header.target.region == "header"
    assert header.target.excluded_page_types == ["TP1"]
    assert header.checks[0].expected == DOCUMENT_TYPE_PATTERN
    assert tp1.target.page_type == "TP1"
    assert tp1.target.region == "body"
    assert tp1.checks[0].expected == DOCUMENT_TYPE_PATTERN
    assert "ATA\\s+No" in HIGHLIGHTS_DOCUMENT_TYPE_PATTERN


def test_highlights_document_type_keeps_special_operator_contract() -> None:
    definition = CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE
    check = definition.compiled_rule.checks[0]

    assert definition.compiled_rule.target.page_type == "HIGHLIGHTS_PAGE_1"
    assert check.operator == "client_operation"
    assert check.operation == "highlights_document_type"
    assert check.missing_anchor == r"(?i)\bATA\s+No\b"
    assert check.missing_anchor_position == "above"


def test_highlights_legend_footer_rule_uses_the_highlights_page_scope() -> None:
    definition = CUSTOM_HIGHLIGHTS_LEGEND_FOOTER
    check = definition.compiled_rule.checks[0]

    assert definition.compiled_rule.target.page_types == [
        "HIGHLIGHTS",
        "HIGHLIGHTS_PAGE_1",
    ]
    assert check.operator == "client_operation"
    assert check.operation == "highlights_legend_footer"
    assert "sans ligne de texte" in definition.description


def test_shop_verification_keeps_manufacturer_context_and_special_operator() -> None:
    definition = CUSTOM_INTRODUCTION_SHOP_VERIFICATION
    check = definition.compiled_rule.checks[0]

    assert definition.compiled_rule.target.page_type == "INTRODUCTION"
    assert definition.compiled_rule.only_if is not None
    assert definition.compiled_rule.only_if.field == "meta_manufacturer"
    assert check.operator == "client_operation"
    assert check.operation == "shop_verification"


def test_highlights_holder_keeps_tp1_title_operator_contract() -> None:
    definition = CUSTOM_HIGHLIGHTS_HOLDER
    check = definition.compiled_rule.checks[0]

    assert definition.compiled_rule.target.page_type == "HIGHLIGHTS_PAGE_1"
    assert check.operator == "client_operation"
    assert check.operation == "highlights_holder"


def test_punctuation_and_pressure_rules_keep_their_operation_parameters() -> None:
    punctuation = CUSTOM_SENTENCE_PUNCTUATION.compiled_rule.checks[0]
    punctuation_swap = CUSTOM_ENUMERATION_PUNCTUATION_SWAP.compiled_rule.checks[0]
    pressure = CUSTOM_BAR_PSI_CONVERSION.compiled_rule.checks[0]

    assert punctuation.operator == "sentence_punctuation"
    assert punctuation.expected == "missing_required_punctuation"
    assert CUSTOM_SENTENCE_PUNCTUATION.compiled_rule.severity == "error"
    assert punctuation_swap.operator == "sentence_punctuation"
    assert punctuation_swap.expected == "enumeration_punctuation_swap"
    assert CUSTOM_ENUMERATION_PUNCTUATION_SWAP.compiled_rule.severity == "info"
    assert pressure.operator == "pressure_conversion"
    assert pressure.expected == "bar_to_psi"


def test_si_conversion_rules_use_supported_policies_on_modified_pages() -> None:
    definitions_and_policies = (
        (CUSTOM_PASCAL_INHG_CONVERSION, "pascal_to_inhg"),
        (CUSTOM_METRIC_LENGTH_INCH_CONVERSION, "metric_length_to_inch"),
        (CUSTOM_METRIC_MASS_LBF_CONVERSION, "metric_mass_to_lb"),
        (CUSTOM_METRIC_TORQUE_LBF_IN_CONVERSION, "metric_torque_to_lbf_in"),
    )

    for definition, policy in definitions_and_policies:
        check = definition.compiled_rule.checks[0]
        assert definition.compiled_rule.severity == "error"
        assert definition.compiled_rule.target.page_state == "modified"
        assert check.operator == "unit_conversion"
        assert check.expected == policy

    assert "conversion numerique en lb" in CUSTOM_METRIC_MASS_LBF_CONVERSION.description


def test_paragraph_justification_is_visual_and_scoped_to_modified_pages() -> None:
    definition = CUSTOM_PARAGRAPH_JUSTIFICATION
    check = definition.compiled_rule.checks[0]

    assert definition.compiled_rule.severity == "warning"
    assert definition.compiled_rule.target.page_state == "modified"
    assert definition.compiled_rule.target.region == "full_page"
    assert definition.compiled_rule.target.excluded_page_types == [
        "TP1",
        "TP2",
        "HIGHLIGHTS",
        "HIGHLIGHTS_PAGE_1",
    ]
    assert check.operator == "client_operation"
    assert check.operation == "paragraph_justification"
    assert "geometrie du PDF" in definition.description


def test_note_rules_keep_page_scopes_check_counts_and_storage_anchor() -> None:
    repair = CUSTOM_REPAIR_NOTE.compiled_rule
    testing = CUSTOM_TESTING_NOTE.compiled_rule
    storage = CUSTOM_STORAGE_NOTE.compiled_rule

    assert repair.target.page_type == "REPAIR"
    assert len(repair.checks) == 2
    assert testing.target.page_type == "TESTING"
    assert len(testing.checks) == 3
    assert storage.target.page_type == "STORAGE"
    assert len(storage.checks) == 3
    assert storage.checks[2].missing_anchor == r"(?i)\bRelative\s+humidity\s*:"
    assert storage.checks[2].missing_anchor_position == "below"


def test_tp1_address_rule_keeps_each_address_line_and_relative_anchor() -> None:
    rule = CUSTOM_TP1_THALES_ADDRESS.compiled_rule

    assert rule.target.page_type == "TP1"
    assert len(rule.checks) == 5
    assert [check.missing_anchor_position for check in rule.checks] == [
        "above",
        "above",
        "above",
        "above",
        "below",
    ]
    assert [check.expected_display for check in rule.checks] == [
        "(F9111)",
        "75-77 Avenue Marcel Dassault",
        "33700 Mérignac - France",
        "Tel : +33 (0)5 24 44 77 40",
        "www.thalesgroup.com",
    ]


def test_footer_page_number_keeps_revision_consistency_contract() -> None:
    rule = CUSTOM_FOOTER_PAGE_NUMBER.compiled_rule

    assert rule.severity == "error"
    assert rule.target.region == "full_page"
    assert rule.only_if is not None
    assert rule.only_if.field == "meta_revision_date"
    assert rule.checks[0].operator == "client_operation"
    assert rule.checks[0].operation == "revision_consistency"
    assert rule.checks[0].operation_params == {"control": "footer_page_number"}