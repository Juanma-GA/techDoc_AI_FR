"""Standalone deterministic rule for HIGHLIGHTS RFU statuses."""

from app.checks.thales_rules.rule_factory import build_rule
from app.core.compiled_rules import Check, RuleTarget

S1000D_HIGHLIGHTS_RFU_STATUS = build_rule(
    "THALES-S1000D",
    "v1",
    code="S1000D_HIGHLIGHTS_RFU_STATUS",
    name="HIGHLIGHTS : statut LOEDM des DMC avec reason for update",
    description=(
        "Chaque DMC ayant une reason for update dans HIGHLIGHTS doit être présent "
        "dans la LOEDM avec le statut C (changed) ou R (revised)."
    ),
    message="Un DMC avec reason for update n'a pas le statut C ou R dans la LOEDM.",
    kind="field_consistency",
    severity="error",
    target=RuleTarget(page="all", region="full_page"),
    checks=[
        Check(
            field="text",
            operator="client_operation",
            operation="s1000d_highlights_status",
        )
    ],
    failure_message="statut LOEDM différent de C ou R pour un DMC avec RFU.",
    translations={
        "en": {
            "description": (
                "Every DMC with a reason for update in HIGHLIGHTS must be present "
                "in the LOEDM with status C (changed) or R (revised)."
            ),
            "message": "A DMC with a reason for update does not have LOEDM status C or R.",
        }
    },
)
