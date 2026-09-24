"""Backward-compatible facade for the THALES client bundle."""

from __future__ import annotations

from app.checks.thales_rules.operations import (
    HIGHLIGHTS_HOLDER_PREFIX,
    highlights_content,
    highlights_document_type_expected,
    highlights_document_type_matches,
    highlights_document_type_observed,
    highlights_holder_expected,
    highlights_holder_matches,
    highlights_holder_observed,
    revision_state,
    shop_verification_matches,
    shop_verification_section,
    shop_verification_text,
    tp1_title,
)
from app.checks.thales_rules.page_classifier import (
    HIGHLIGHTS_FIRST_PAGE_TYPE,
    HIGHLIGHTS_PAGE_TYPE,
    INTRODUCTION_PAGE_TYPE,
    REPAIR_PAGE_TYPE,
    STORAGE_PAGE_TYPE,
    TESTING_PAGE_TYPE,
    TP1_PAGE_TYPE,
    TP2_PAGE_TYPE,
    classify_pages,
    identify_introduction_pages,
    identify_note_pages,
    identify_page_type,
    identify_tp1_pages,
)
from app.checks.thales_rules.rules import (
    CATALOG,
    DOCUMENT_TYPE_PATTERN as _DOCUMENT_TYPE_PATTERN,
    DOCUMENT_TYPES as _DOCUMENT_TYPES,
    HIGHLIGHTS_DOCUMENT_TYPE_PATTERN as _HIGHLIGHTS_DOCUMENT_TYPE_PATTERN,
    IMPORTANT_NOTICE_TEXT as _IMPORTANT_NOTICE_TEXT,
    REVISION_RULE_DEFINITIONS,
    RULE_METADATA,
    RULE_DEFINITIONS,
    STANDARD_SPEC,
)
from app.checks.thales_rules.operations import OPERATIONS
from app.core.compiled_rules import CompiledRule
from app.core.compiled_rule_operators import register_client_operation


STANDARD_CODE = "THALES-CUSTOM"
STANDARD_LABEL = str(STANDARD_SPEC["label"])
STANDARD_DESCRIPTION = str(STANDARD_SPEC["description"])

_REVISION_RULES = [
    definition.compiled_rule for definition in REVISION_RULE_DEFINITIONS
]
_RULES_V1 = [definition.compiled_rule for definition in RULE_DEFINITIONS]
for _operation in OPERATIONS.values():
    register_client_operation(_operation)
