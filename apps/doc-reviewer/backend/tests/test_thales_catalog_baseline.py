from __future__ import annotations

import hashlib
import json

from app.checks.client_registry import load_active_client_configuration
from app.checks.standards import serialize_builtin_version


def test_thales_v1_catalog_matches_bundle_operation_baseline() -> None:
    configuration = load_active_client_configuration()
    spec = configuration.bundle.standard_specs["THALES-CUSTOM"]
    payload = serialize_builtin_version(spec, "v1")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    assert len(payload) == 55
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == (
        "1e65d11967145802753108e520eab850f5c9e25472817db89816cab1038eeadb"
    )

    expected_controls = {
        "CUSTOM_REVISION_LEP_STAR": "lep_star",
        "CUSTOM_REVISION_UNDECLARED_STAR": "undeclared_star",
        "CUSTOM_REVISION_HIGHLIGHTS_STATUS": "highlights_status_consistency",
        "CUSTOM_REVISION_LEP_BLANK_STAR": "blank_lep_star",
        "CUSTOM_REVISION_LEP_DATE": "lep_date",
        "CUSTOM_REVISION_FOOTER_DATE": "footer_date",
        "CUSTOM_FOOTER_PAGE_NUMBER": "footer_page_number",
        "CUSTOM_REVISION_UNDECLARED_PAGE": "undeclared_page",
        "CUSTOM_REVISION_PAGE_NOT_IN_LEP": "page_not_in_lep",
        "CUSTOM_REVISION_MODIFIED_PAGE_ABSENT": "modified_page_absent",
        "CUSTOM_HIGHLIGHTS_PAGE_PAIRING": "highlights_pairing",
        "CUSTOM_HIGHLIGHTS_PAGE_LABEL_FORMAT": "highlights_page_label",
        "CUSTOM_ROR_INSERTION_DATE": "ror_insertion_date",
        "CUSTOM_ROR_REVISION_DATE": "ror_revision_date",
    }
    by_code = {item["code"]: item for item in payload}
    for code, control in expected_controls.items():
        check = by_code[code]["checks"][0]
        assert check["operator"] == "client_operation"
        assert check["operation"] == "revision_consistency"
        assert check["operation_params"] == {"control": control}
        assert check["expected"] is None

    expected_operations = {
        "CUSTOM_INTRODUCTION_SHOP_VERIFICATION": ("shop_verification", {}),
        "CUSTOM_HIGHLIGHTS_HOLDER": ("highlights_holder", {}),
        "CUSTOM_HIGHLIGHTS_DOCUMENT_TYPE": ("highlights_document_type", {}),
        "CUSTOM_HIGHLIGHTS_DELETION_DESCRIPTION": (
            "document_structure",
            {"control": "highlights_deleted_description"},
        ),
        "CUSTOM_HIGHLIGHTS_REVISED_DESCRIPTION": (
            "document_structure",
            {"control": "highlights_revised_description"},
        ),
        "CUSTOM_CHAPTER_NUMBER_SEQUENCE": (
            "document_structure",
            {"control": "chapter_sequence"},
        ),
        "CUSTOM_HIGHLIGHTS_LEGEND_FOOTER": ("highlights_legend_footer", {}),
        "CUSTOM_COPYRIGHT_POSITION": ("copyright_position", {}),
        "CUSTOM_PARAGRAPH_JUSTIFICATION": ("paragraph_justification", {}),
    }
    for code, (operation, operation_params) in expected_operations.items():
        check = by_code[code]["checks"][0]
        assert check["operator"] == "client_operation"
        assert check["operation"] == operation
        assert check["operation_params"] == operation_params
        assert check["expected"] is None

    expected_conversions = {
        "CUSTOM_PASCAL_INHG_CONVERSION": "pascal_to_inhg",
        "CUSTOM_METRIC_LENGTH_INCH_CONVERSION": "metric_length_to_inch",
        "CUSTOM_METRIC_MASS_LBF_CONVERSION": "metric_mass_to_lb",
        "CUSTOM_METRIC_TORQUE_LBF_IN_CONVERSION": "metric_torque_to_lbf_in",
    }
    for code, policy in expected_conversions.items():
        check = by_code[code]["checks"][0]
        assert check["operator"] == "unit_conversion"
        assert check["expected"] == policy